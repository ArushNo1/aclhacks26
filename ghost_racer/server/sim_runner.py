"""Headless 20 Hz sim loop. Owns GhostRacerEnv and pushes per-tick snapshots
into SimState. Heavy renders (spectator, player_3d, policy obs) are cached
on `self` so MJPEG endpoints can read the latest frame without re-stepping.

Lifecycle:
  runner = SimRunner(state, ...)
  await runner.start()    # spawns the asyncio tick loop
  ...
  await runner.stop()
"""
from __future__ import annotations

import asyncio
import math
import os
import time
from typing import Awaitable, Callable, Optional

import numpy as np


# Keep heavy imports local so unrelated tools (linters, docs) don't trigger
# pygame/torch on import.
def _import_env():
    from ..sim.env import GhostRacerEnv  # noqa: WPS433
    return GhostRacerEnv


class SimRunner:
    """Runs the env at 20 Hz, updates SimState, caches the latest frames."""

    def __init__(
        self,
        state,
        bc_policy_path: str = "ghost_racer/data/bc_policy.pt",
        rl_policy_path: str = "ghost_racer/data/rl_policy.zip",
        data_dir: str = "ghost_racer/data",
    ) -> None:
        self.state = state
        self.bc_policy_path = bc_policy_path
        self.rl_policy_path = rl_policy_path
        self.data_dir = data_dir

        self.dt = 0.05  # 20 Hz
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

        # Set in start()
        self.env = None
        self._policies: dict = {"bc": None, "rl": None, "none": None}
        self.active_policy: str = "none"

        # Cached observation for AI policy (computed at end of step())
        self._ai_obs: Optional[np.ndarray] = None
        # Cached frames for MJPEG endpoints
        self.last_spectator: Optional[np.ndarray] = None      # 600x600x3 RGB
        self.last_player_view: Optional[np.ndarray] = None     # 240x320x3 RGB
        self.last_ai_view: Optional[np.ndarray] = None         # 120x160x3 RGB

        # Race timing
        self._race_started_at: Optional[float] = None  # monotonic time when lights turned green
        self._light_task: Optional[asyncio.Task] = None

        # Lap detection: track previous lap counts so we can record times.
        self._prev_lap_ego = 0
        self._prev_lap_opp = 0

        # Optional pluggable hand action source (laptop/hand_drive style).
        # If set, called every tick and returns (steer, throttle, has_left, has_right).
        self.hand_action_provider: Optional[Callable[[], dict]] = None

        # Hand capture runner (webcam + MediaPipe). Attached in start() if a
        # webcam is available; otherwise the runner falls back to the
        # autopilot. Browser-driven calibration goes through this object.
        self.hand_runner = None

        # Recorder + trainer (filled in by Capture/Train phases)
        self.recorder = None
        self.training_manager = None

    # ----------------------------------------------------------- lifecycle
    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.state.attach_loop(loop)

        GhostRacerEnv = _import_env()
        self.env = GhostRacerEnv(opponent_policy=None)
        obs, _ = self.env.reset()
        self._ai_obs = obs

        # Load whichever policy is on disk; pick BC if present.
        self._reload_policies()
        if self._policies["bc"] is not None:
            self.active_policy = "bc"
        else:
            self.active_policy = "none"
        with self.state.lock():
            self.state.policy_active = self.active_policy
            self.state.policy_version = self._policy_version_from_disk()

        # Pre-render once so MJPEG endpoints have something to serve immediately
        self._render_frames()

        # Attach the webcam-based hand runner if we have a camera. This is a
        # best-effort: on machines without a webcam we silently fall back to
        # the autopilot so the rest of the dashboard keeps working.
        try:
            from .hand_runner import HandCaptureRunner
            self.hand_runner = HandCaptureRunner(self.state)
            ok = self.hand_runner.start()
            if ok:
                # Drive the env from the live hand reading
                runner = self.hand_runner

                def _provider() -> dict:
                    r = runner.last_reading
                    if r is None:
                        return {"steer": 0.0, "throttle": 0.0,
                                "has_left": False, "has_right": False,
                                "raw_left_size": 0.0, "raw_right_size": 0.0}
                    return {
                        "steer": float(r.steer),
                        "throttle": float(r.throttle),
                        "has_left": bool(r.has_left),
                        "has_right": bool(r.has_right),
                        "raw_left_size": float(r.raw_left_size),
                        "raw_right_size": float(r.raw_right_size),
                    }
                self.hand_action_provider = _provider
        except Exception as e:
            print(f"[sim_runner] hand runner init failed: {e}")
            self.hand_runner = None

        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="sim-runner")

    async def stop(self) -> None:
        self._stop.set()
        if self._light_task is not None:
            self._light_task.cancel()
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.hand_runner is not None:
            try:
                self.hand_runner.stop()
            except Exception:
                pass
            self.hand_runner = None
        if self.env is not None:
            # GhostRacerEnv has no close, but it's harmless to drop
            self.env = None

    # ----------------------------------------------------------- tick loop
    async def _loop(self) -> None:
        loop = asyncio.get_running_loop()
        next_tick = loop.time()
        last_real = time.time()
        while not self._stop.is_set():
            self._tick(last_real)
            last_real = time.time()
            self.state.publish()
            next_tick += self.dt
            delay = next_tick - loop.time()
            if delay < -0.5:
                # we got way behind (debug breakpoint, slow render)
                next_tick = loop.time()
            elif delay > 0:
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    return

    def _tick(self, last_real_t: float) -> None:
        # 1. read hand action (or default to neutral)
        if self.hand_action_provider is not None:
            hand = self.hand_action_provider()
            steer = float(hand.get("steer", 0.0))
            throttle = float(hand.get("throttle", 0.0))
            with self.state.lock():
                self.state.hand.has_left = bool(hand.get("has_left", False))
                self.state.hand.has_right = bool(hand.get("has_right", False))
                self.state.hand.steer = steer
                self.state.hand.throttle = throttle
                self.state.hand.raw_left_size = float(hand.get("raw_left_size", 0.0))
                self.state.hand.raw_right_size = float(hand.get("raw_right_size", 0.0))
            human_action = np.array([steer, throttle], dtype=np.float32)
        else:
            # Server-side autopilot for the human slot until a hand source attaches
            t = time.time()
            steer = 0.55 * math.sin(0.6 * t)  # gentle weave
            throttle = 0.55
            with self.state.lock():
                self.state.hand.has_left = False
                self.state.hand.has_right = False
                self.state.hand.steer = steer
                self.state.hand.throttle = throttle
            human_action = np.array([steer, throttle], dtype=np.float32)

        # 2. AI action
        if self.active_policy == "none" or self._policies.get(self.active_policy) is None:
            ai_action = np.array([0.0, 0.5], dtype=np.float32)  # cruise
        else:
            try:
                ai_action = self._policies[self.active_policy](self._ai_obs)
            except Exception:
                ai_action = np.array([0.0, 0.5], dtype=np.float32)

        # 3. Recording (if enabled, push opponent's POV pre-step)
        if self.recorder is not None:
            try:
                human_obs = self.env._obs(self.env.opp, self.env.ego)
                self.recorder.push(human_obs, float(steer), float(throttle))
                with self.state.lock():
                    self.state.capture.frames = len(self.recorder)
            except Exception:
                pass

        # 4. step env
        self._ai_obs, reward, terminated, truncated, info = self.env.step(
            ai_action, opp_action=human_action
        )

        # 5. render frames for MJPEG endpoints
        self._render_frames()

        # 6. update race / lap state
        self._update_race_state(info)

        # 7. fps
        with self.state.lock():
            dt_real = time.time() - last_real_t
            self.state.fps = 1.0 / max(1e-3, dt_real)
            self.state.tick += 1
            self.state.policy_active = self.active_policy

    # --------------------------------------------------------- frame cache
    def _render_frames(self) -> None:
        try:
            self.last_spectator = self.env.render()
        except Exception:
            pass
        try:
            self.last_player_view = self.env.render_player_3d(H=240, W=320)
        except Exception:
            pass
        if self._ai_obs is not None:
            self.last_ai_view = self._ai_obs

    # ----------------------------------------------------- race/lap state
    def _update_race_state(self, info: dict) -> None:
        track = self.env.track
        ex, ey = self.env.ego.position
        ox, oy = self.env.opp.position
        ego_progress = float(track.progress_normalized(ex, ey))
        opp_progress = float(track.progress_normalized(ox, oy))

        with self.state.lock():
            r = self.state.race
            # car1 = human/opp, car2 = AI/ego
            r.car1.position_on_track = opp_progress
            r.car2.position_on_track = ego_progress
            r.car1.speed = float(self.env.opp.speed)
            r.car2.speed = float(self.env.ego.speed)
            r.off_track = bool(info.get("off_track", False))
            r.collision = bool(info.get("collision", False))

            # lap-count edge detection -> push lap times
            new_lap_ego = int(info.get("lap_ego", 0))
            new_lap_opp = int(info.get("lap_opp", 0))
            if r.started and self._race_started_at is not None:
                clock = time.monotonic() - self._race_started_at
                r.race_clock = clock
                if new_lap_opp > self._prev_lap_opp:
                    r.car1.lap_times.append(round(clock, 3))
                    r.car1.lap_count = new_lap_opp
                    r.car1.last_lap_s, r.car1.best_lap_s = _lap_stats(r.car1.lap_times)
                if new_lap_ego > self._prev_lap_ego:
                    r.car2.lap_times.append(round(clock, 3))
                    r.car2.lap_count = new_lap_ego
                    r.car2.last_lap_s, r.car2.best_lap_s = _lap_stats(r.car2.lap_times)
            self._prev_lap_ego = new_lap_ego
            self._prev_lap_opp = new_lap_opp

    # ----------------------------------------------------- public commands
    def reset_env(self) -> None:
        if self.env is None:
            return
        obs, _ = self.env.reset()
        self._ai_obs = obs
        self._prev_lap_ego = 0
        self._prev_lap_opp = 0
        with self.state.lock():
            r = self.state.race
            r.car1 = type(r.car1)()  # fresh CarSnapshot
            r.car2 = type(r.car2)()
            r.race_clock = 0.0
            r.off_track = False
            r.collision = False

    async def start_race(self) -> None:
        """Trigger the staged red/yellow/green sequence and switch phase to
        'race'. Resets lap counts."""
        self.reset_env()
        with self.state.lock():
            self.state.phase = "race"
            self.state.race.light_phase = "off"
            self.state.race.started = False
        self._race_started_at = None

        # Cancel any in-flight light sequence
        if self._light_task is not None and not self._light_task.done():
            self._light_task.cancel()
        self._light_task = asyncio.create_task(self._light_sequence())

    async def _light_sequence(self) -> None:
        """Match the frontend's prior cadence: off → red @600ms → yellow @1000ms → green @1200ms."""
        try:
            await asyncio.sleep(0.6)
            with self.state.lock():
                self.state.race.light_phase = "red"
            await asyncio.sleep(1.0)
            with self.state.lock():
                self.state.race.light_phase = "yellow"
            await asyncio.sleep(1.2)
            with self.state.lock():
                self.state.race.light_phase = "green"
                self.state.race.started = True
            self._race_started_at = time.monotonic()
        except asyncio.CancelledError:
            return

    def reset_race(self) -> None:
        if self._light_task is not None and not self._light_task.done():
            self._light_task.cancel()
        self._race_started_at = None
        with self.state.lock():
            self.state.phase = "idle"
            self.state.race.light_phase = "off"
            self.state.race.started = False
            self.state.race.race_clock = 0.0
        self.reset_env()

    def set_active_policy(self, name: str) -> None:
        if name not in ("none", "bc", "rl"):
            raise ValueError(f"unknown policy: {name}")
        if name != "none" and self._policies.get(name) is None:
            raise ValueError(f"no {name} policy loaded")
        self.active_policy = name
        with self.state.lock():
            self.state.policy_active = name

    def reload_bc(self) -> Optional[str]:
        """Reload the BC checkpoint from disk and bump the policy version
        if it loaded successfully."""
        bc = self._load_bc()
        if bc is None:
            return None
        self._policies["bc"] = bc
        version = self._policy_version_from_disk()
        with self.state.lock():
            self.state.policy_version = version
            self.state.training.policy_version = version
        return version

    # ---------------------------------------------------------- internals
    def _reload_policies(self) -> None:
        self._policies["bc"] = self._load_bc()
        self._policies["rl"] = self._load_rl()

    def _load_bc(self):
        if not os.path.exists(self.bc_policy_path):
            return None
        try:
            import torch
            from ..agent.policy import PolicyCNN, policy_act
            ckpt = torch.load(self.bc_policy_path, map_location="cpu", weights_only=False)
            policy = PolicyCNN(input_shape=ckpt.get("input_shape", (3, 120, 160)))
            policy.load_state_dict(ckpt["state_dict"])
            policy.eval()
            return lambda obs: policy_act(policy, obs, device="cpu")
        except Exception as e:
            print(f"[sim_runner] BC load failed: {e}")
            return None

    def _load_rl(self):
        if not os.path.exists(self.rl_policy_path):
            return None
        try:
            from stable_baselines3 import PPO
            model = PPO.load(self.rl_policy_path, device="cpu")

            def act(obs: np.ndarray) -> np.ndarray:
                a, _ = model.predict(obs, deterministic=True)
                return np.asarray(a, dtype=np.float32).reshape(2)
            return act
        except Exception as e:
            print(f"[sim_runner] RL load failed: {e}")
            return None

    def _policy_version_from_disk(self) -> Optional[str]:
        if not os.path.exists(self.bc_policy_path):
            return None
        # Use mtime as a monotonically-bumping version label
        ts = int(os.path.getmtime(self.bc_policy_path))
        return f"v{ts:x}"


def _lap_stats(times):
    """Given cumulative lap times (with leading 0.0), return (last_lap_s, best_lap_s)."""
    if len(times) < 2:
        return None, None
    last = float(times[-1] - times[-2])
    best = min(float(times[i] - times[i - 1]) for i in range(1, len(times)))
    return last, best
