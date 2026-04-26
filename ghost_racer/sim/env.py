"""
Gymnasium env for a 2-car race. The "ego" car is the learning agent; the
"opponent" car is driven by an externally-supplied policy callable (or by
a recorded human trajectory). The same env is used at training time for the
agent and at demo time with a human in the opponent slot.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .car import Car, cars_collide
from .domain_rand import DomainRand
from .render import render_first_person
from .track import Track


OPPONENT_POLICY = Callable[[np.ndarray], np.ndarray]
# signature: takes an obs (HxWx3 uint8) and returns (steer, throttle).


class GhostRacerEnv(gym.Env):
    """Ego learns to overtake the opponent. Opponent is supplied externally."""

    metadata = {"render_modes": ["rgb_array"], "render_fps": 30}

    def __init__(
        self,
        opponent_policy: Optional[OPPONENT_POLICY] = None,
        domain_rand: bool = False,
        obs_height: int = 120,
        obs_width: int = 160,
        dt: float = 0.05,
        max_episode_steps: int = 1500,
        randomize_start: bool = True,
    ):
        super().__init__()
        self.track = Track()
        self.dt = dt
        self.obs_h = obs_height
        self.obs_w = obs_width
        self.max_episode_steps = max_episode_steps
        self.randomize_start = randomize_start

        self.dr = DomainRand(enabled=domain_rand)
        self.opponent_policy = opponent_policy

        self.ego = Car()
        self.opp = Car()
        self.steps = 0

        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32)
        self.observation_space = spaces.Box(
            low=0, high=255, shape=(obs_height, obs_width, 3), dtype=np.uint8
        )

        self._prev_progress_ego = 0.0
        self._prev_progress_opp = 0.0
        self._last_xy_ego: Tuple[float, float] = (0.0, 0.0)
        self._last_xy_opp: Tuple[float, float] = (0.0, 0.0)
        self.lap_ego = 0
        self.lap_opp = 0
        self._stuck_steps = 0
        self._np_random = np.random.default_rng()

    # ------------------------------------------------------------------ API
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._np_random = np.random.default_rng(seed)
        self.dr.rng = self._np_random
        self.dr.resample()

        if self.randomize_start:
            ex, ey, eth = self._random_pose(lateral_jitter=0.25)
            # opponent ~1m ahead along the track so ego is the chaser
            ox, oy, oth = self._pose_offset(ex, ey, eth, forward_m=1.0)
        else:
            # Stagger: ego (learner) starts behind so overtaking is the natural objective
            ex, ey, eth = self.track.start_pose(slot=1)
            ox, oy, oth = self.track.start_pose(slot=0)
        self.ego.reset(ex, ey, eth)
        self.opp.reset(ox, oy, oth)

        self.steps = 0
        self.lap_ego = 0
        self.lap_opp = 0
        self._stuck_steps = 0
        self._prev_progress_ego = self.track.progress_normalized(*self.ego.position)
        self._prev_progress_opp = self.track.progress_normalized(*self.opp.position)
        self._last_xy_ego = self.ego.position
        self._last_xy_opp = self.opp.position

        return self._obs(self.ego, self.opp), {}

    def _random_pose(self, lateral_jitter: float = 0.0) -> Tuple[float, float, float]:
        """Pick a random waypoint on the centerline, return pose pointing along
        the track tangent. Optional lateral jitter shifts the car off the
        centerline so the agent sees recovery situations."""
        wp = self.track.waypoints
        idx = int(self._np_random.integers(0, len(wp)))
        nxt = (idx + 1) % len(wp)
        p = wp[idx]
        q = wp[nxt]
        tangent = q - p
        tnorm = float(np.linalg.norm(tangent)) + 1e-9
        tx, ty = float(tangent[0] / tnorm), float(tangent[1] / tnorm)
        theta = float(np.arctan2(ty, tx))
        if lateral_jitter > 0.0:
            half = self.track.track_width / 2.0 - 0.05
            jitter = float(self._np_random.uniform(-min(lateral_jitter, half),
                                                    min(lateral_jitter, half)))
            # left-hand normal
            nx, ny = -ty, tx
            x = float(p[0]) + jitter * nx
            y = float(p[1]) + jitter * ny
        else:
            x, y = float(p[0]), float(p[1])
        return x, y, theta

    @staticmethod
    def _pose_offset(x: float, y: float, theta: float, forward_m: float
                     ) -> Tuple[float, float, float]:
        import math
        return x + forward_m * math.cos(theta), y + forward_m * math.sin(theta), theta

    def step(self, action, opp_action=None):
        """If `opp_action` is supplied (e.g. play.py passing the human's hand
        reading), the opponent's first-person view is NOT rendered, saving the
        most expensive op in the loop.
        """
        action = np.asarray(action, dtype=np.float32).reshape(2)

        if opp_action is not None:
            opp_action = np.asarray(opp_action, dtype=np.float32).reshape(2)
        elif self.opponent_policy is None:
            opp_action = np.array([0.0, 0.4], dtype=np.float32)  # default cruise
        else:
            opp_obs = self._obs(self.opp, self.ego)
            opp_action = np.asarray(self.opponent_policy(opp_obs), dtype=np.float32).reshape(2)

        self.ego.step(action[0], action[1], self.dt)
        self.opp.step(opp_action[0], opp_action[1], self.dt)

        # hard track walls: clamp both cars back inside the corridor and
        # bleed speed on contact so they can't drive through the grass
        ego_hit = self._enforce_walls(self.ego)
        opp_hit = self._enforce_walls(self.opp)

        # progress and lap detection. Use lap-aware totals so wrap-around at
        # the finish line doesn't produce a giant negative delta.
        prog_ego = self._lap_progress(self.ego, self._last_xy_ego, self._prev_progress_ego, "ego")
        prog_opp = self._lap_progress(self.opp, self._last_xy_opp, self._prev_progress_opp, "opp")
        ego_total = self.lap_ego + prog_ego
        opp_total = self.lap_opp + prog_opp
        prev_ego_total = self.lap_ego + self._prev_progress_ego
        prev_opp_total = self.lap_opp + self._prev_progress_opp
        # the lap counter just ticked above, so "prev" needs to subtract the
        # lap that was added by _lap_progress for ego/opp respectively
        if prog_ego < self._prev_progress_ego and ego_total > prev_ego_total:
            prev_ego_total -= 1  # finish-line crossing this step
        if prog_opp < self._prev_progress_opp and opp_total > prev_opp_total:
            prev_opp_total -= 1
        d_ego_m = (ego_total - prev_ego_total) * self.track.total_length
        d_opp_m = (opp_total - prev_opp_total) * self.track.total_length

        # reward shaping
        off_track_ego = ego_hit
        collision = cars_collide(self.ego, self.opp)

        # track "stuck" — barely making forward progress for many steps in a row.
        # Wall bouncing alternates hit/no-hit each step, so we key off progress
        # rather than continuous contact.
        if d_ego_m < 0.005:
            self._stuck_steps += 1
        elif d_ego_m > 0.02:
            self._stuck_steps = 0
        # else: in-between progress doesn't reset, but doesn't increment either

        reward = 0.0
        reward += 2.0 * d_ego_m                            # progress
        reward += 0.5 * (d_ego_m - d_opp_m)                # closing the gap
        reward -= 0.5 if ego_hit else 0.0                  # wall-contact penalty
        # escalating penalty as the car remains stuck (capped to keep returns sane)
        reward -= 0.05 * min(self._stuck_steps, 40)
        reward -= 1.0 if collision else 0.0                # don't bump

        # overtake bonus: ego's cumulative lap-progress passes opp's
        if (prev_ego_total < prev_opp_total) and (ego_total >= opp_total):
            reward += 5.0  # passed!

        self._prev_progress_ego = prog_ego
        self._prev_progress_opp = prog_opp
        self._last_xy_ego = self.ego.position
        self._last_xy_opp = self.opp.position

        self.steps += 1
        # end the episode early if we've been wedged against a wall — gives PPO
        # a clean negative-return signal instead of hundreds of "stuck" frames
        stuck_out = self._stuck_steps >= 60
        terminated = (collision and self.steps > 5) or stuck_out
        truncated = self.steps >= self.max_episode_steps

        info = {
            "lap_ego": self.lap_ego,
            "lap_opp": self.lap_opp,
            "off_track": off_track_ego,
            "collision": collision,
            "ego_progress": ego_total,
            "opp_progress": opp_total,
            "stuck_steps": self._stuck_steps,
        }
        obs = self._obs(self.ego, self.opp)
        return obs, float(reward), terminated, truncated, info

    # ------------------------------------------------------------------ internal
    def _enforce_walls(self, car: Car) -> bool:
        """Push the car back inside the track corridor if it left, and
        scrub speed on contact. Returns True if a wall was hit."""
        nx, ny, hit = self.track.clamp_to_corridor(*car.position)
        if hit:
            car.state.x = nx
            car.state.y = ny
            # scrub speed; preserves sign so the car doesn't reverse off the wall
            car.state.v *= 0.35
        return hit

    def _obs(self, ego: Car, opp: Car) -> np.ndarray:
        return render_first_person(self.track, ego, opp, self.dr, H=self.obs_h, W=self.obs_w)

    def _lap_progress(self, car, last_xy, prev_norm, who: str) -> float:
        """Return current normalized progress; bump lap counter on finish-line crossing."""
        prog = self.track.progress_normalized(*car.position)
        if self.track.finish_line_crossed(last_xy, car.position):
            if who == "ego":
                self.lap_ego += 1
            else:
                self.lap_opp += 1
        return prog

    def render(self):
        from .render import render_spectator
        return render_spectator(self.track, [self.ego, self.opp], self.dr)

    def render_player_3d(self, H: int = 240, W: int = 320) -> np.ndarray:
        """Perspective 3D camera mounted on the human-driven car (opp slot).
        Used as a navigation aid in the human window — the AI policy keeps
        its cheap bird's-eye observation."""
        from .render import render_player_3d
        return render_player_3d(self.track, self.opp, self.ego, self.dr, H=H, W=W)
