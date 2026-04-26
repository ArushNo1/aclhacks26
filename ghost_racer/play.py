"""
Demo entry point: human (hand) drives one car, AI policy drives the other.

  python -m ghost_racer.play                          # auto-loads BC if present, else cruise
  python -m ghost_racer.play --calibrate              # run hand calibration first
  python -m ghost_racer.play --record                 # write training data
  python -m ghost_racer.play --auto-train             # retrain BC after each round

Hot-keys (in pygame window):
  1 = use BC policy           2 = use RL policy           0 = no AI (cruise)
  R = reset env
  S = save current recording
  Q / ESC = quit
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np
import pygame

# Heavy imports (torch, gymnasium, stable_baselines3) are deferred until after
# hand calibration so the calibration window appears immediately after launch.
from .agent.recorder import SessionRecorder
from .control.hand_control import (DEFAULT_CALIB_PATH, HandCalibration,
                                   HandController)


WINDOW_W, WINDOW_H = 1280, 720
SPECTATOR_PX = 600
RIGHT_COL_X = 640
RIGHT_COL_W = 620
PANEL_GAP = 18

LAPS_PER_ROUND = 1   # round ends when human or AI hits this many laps


# ------------------------------------------------------------------ policy loaders
def load_bc_policy(path: str, device: str = "cpu"):
    if not os.path.exists(path):
        return None
    import torch
    from .agent.policy import PolicyCNN, policy_act
    ckpt = torch.load(path, map_location=device, weights_only=False)
    policy = PolicyCNN(input_shape=ckpt.get("input_shape", (3, 120, 160))).to(device)
    policy.load_state_dict(ckpt["state_dict"])
    policy.eval()
    return lambda obs: policy_act(policy, obs, device=device)


def load_rl_policy(path: str):
    if not os.path.exists(path):
        return None
    from stable_baselines3 import PPO
    model = PPO.load(path, device="cpu")

    def act(obs: np.ndarray) -> np.ndarray:
        a, _ = model.predict(obs, deterministic=True)
        return np.asarray(a, dtype=np.float32).reshape(2)
    return act


# ------------------------------------------------------------------ background training
class TrainingManager:
    """Runs BC retraining in a background thread between rounds."""

    def __init__(self, data_dir: str, bc_out: str, epochs: int = 8):
        self.data_dir = data_dir
        self.bc_out = bc_out
        self.epochs = epochs
        self._lock = threading.Lock()
        self.training = False
        self.last_status = "idle"
        self.last_val_mse: Optional[float] = None
        self.pending_reload = False
        self._start_t: Optional[float] = None
        # Per-epoch (epoch, train_loss, val_loss) tuples, drained by the UI pump.
        self._epoch_log: List[Tuple[int, float, float]] = []

    def maybe_start(self) -> bool:
        with self._lock:
            if self.training:
                return False
            self.training = True
            self.last_status = "training BC..."
            self._start_t = time.time()
            self._epoch_log.clear()
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _on_epoch(self, epoch: int, train_loss: float, val_loss: float) -> None:
        with self._lock:
            self._epoch_log.append((epoch, train_loss, val_loss))
            self.last_status = (
                f"epoch {epoch}/{self.epochs}  "
                f"train={train_loss:.4f}  val={val_loss:.4f}"
            )

    def drain_epochs(self) -> List[Tuple[int, float, float]]:
        with self._lock:
            out = list(self._epoch_log)
            self._epoch_log.clear()
            return out

    def _run(self):
        try:
            from .agent.bc_train import train_bc
            best = train_bc(self.data_dir, self.bc_out, epochs=self.epochs,
                            device="cpu", verbose=False, on_epoch=self._on_epoch)
            with self._lock:
                self.last_val_mse = float(best)
                self.last_status = f"BC ready (val={best:.3f})"
                self.pending_reload = True
        except Exception as e:
            with self._lock:
                self.last_status = f"BC failed: {e}"
        finally:
            with self._lock:
                self.training = False

    def status_line(self) -> str:
        with self._lock:
            if self.training and self._start_t is not None:
                return f"{self.last_status} ({time.time() - self._start_t:.0f}s)"
            return self.last_status


# ------------------------------------------------------------------ helpers
def cv_to_pygame(frame_bgr: np.ndarray) -> pygame.Surface:
    """OpenCV BGR HxWx3 -> pygame Surface (RGB)."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))


def fit_to_panel(surface: pygame.Surface, target_w: int, target_h: int) -> pygame.Surface:
    sw, sh = surface.get_size()
    scale = min(target_w / sw, target_h / sh)
    return pygame.transform.smoothscale(surface, (int(sw * scale), int(sh * scale)))


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=["none", "bc", "rl"], default=None,
                    help="Default policy (auto-detects bc if present).")
    ap.add_argument("--bc", default="ghost_racer/data/bc_policy.pt")
    ap.add_argument("--rl", default="ghost_racer/data/rl_policy.zip")
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--skip-calibrate", action="store_true",
                    help="Skip the startup prompt and always use the saved profile.")
    ap.add_argument("--calibrate", action="store_true",
                    help="Force recalibration on startup (skips the use-saved prompt).")
    ap.add_argument("--auto-train", action="store_true",
                    help="Retrain BC after each round on the recorded data.")
    ap.add_argument("--data-dir", default="ghost_racer/data")
    args = ap.parse_args()

    # if user wants auto-train but isn't recording, force-enable record so
    # the rounds actually produce training data
    if args.auto_train and not args.record:
        print("[note] --auto-train implies --record; enabling.", file=sys.stderr)
        args.record = True

    # ------------------------------------------------------------------
    # STEP 1 — HAND CALIBRATION (always, before anything else loads)
    # ------------------------------------------------------------------
    print("=" * 60)
    print(" STEP 1 / 2: HAND CALIBRATION")
    print("=" * 60)
    try:
        ctrl = HandController(args.cam, mirror=not args.no_mirror)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    has_saved = os.path.exists(DEFAULT_CALIB_PATH) and ctrl.calibration.has_arm_data
    if args.calibrate:
        should_calibrate = True
    elif args.skip_calibrate and has_saved:
        should_calibrate = False
        print(f"--skip-calibrate set; using saved calibration at {DEFAULT_CALIB_PATH}")
    elif not has_saved:
        should_calibrate = True
        if os.path.exists(DEFAULT_CALIB_PATH):
            print("[note] saved profile predates arm-rotation steering; recalibrating.")
        else:
            print("no saved calibration found; running first-time calibration.")
    else:
        try:
            use_saved = ctrl.prompt_use_saved(calib_path=DEFAULT_CALIB_PATH)
        except KeyboardInterrupt:
            print("aborted at startup", file=sys.stderr)
            ctrl.close()
            sys.exit(0)
        should_calibrate = not use_saved
        print("user chose:", "RECALIBRATE" if should_calibrate else f"USE SAVED ({DEFAULT_CALIB_PATH})")

    if should_calibrate:
        try:
            ctrl.run_calibration()
            print(f"calibration done; weights saved to {DEFAULT_CALIB_PATH}")
        except KeyboardInterrupt:
            print("calibration aborted; using previous values", file=sys.stderr)

    # ------------------------------------------------------------------
    # STEP 2 — load the rest (heavy imports deferred until now so the
    # calibration window appears immediately after launch).
    # ------------------------------------------------------------------
    print("=" * 60)
    print(" STEP 2 / 2: loading policies + simulator...")
    print("=" * 60)
    from .sim.env import GhostRacerEnv

    policies = {"bc": load_bc_policy(args.bc), "rl": load_rl_policy(args.rl), "none": None}

    if args.agent is None:
        active = "bc" if policies["bc"] is not None else "none"
    else:
        active = args.agent
    if active != "none" and policies.get(active) is None:
        print(f"warning: no {active} policy at expected path; falling back to 'none'",
              file=sys.stderr)
        active = "none"

    # --- env ---
    env = GhostRacerEnv(opponent_policy=None)
    ai_obs, _ = env.reset()  # carries the AI car's POV across frames (cache)

    # --- pygame ---
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Ghost Racer - hand vs clone")
    font = pygame.font.SysFont("monospace", 18)
    small_font = pygame.font.SysFont("monospace", 14)
    clock = pygame.time.Clock()

    # --- recorder + training manager ---
    rec: Optional[SessionRecorder] = SessionRecorder(args.data_dir) if args.record else None
    trainer = TrainingManager(args.data_dir, args.bc, epochs=8) if args.auto_train else None

    last_t = time.time()
    round_msg = ""
    round_msg_until = 0.0
    round_number = 1
    running = True

    while running:
        # ---------------- input ----------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                elif event.key == pygame.K_1 and policies["bc"] is not None:
                    active = "bc"
                elif event.key == pygame.K_2 and policies["rl"] is not None:
                    active = "rl"
                elif event.key == pygame.K_0:
                    active = "none"
                elif event.key == pygame.K_r:
                    ai_obs, _ = env.reset()
                    round_msg = "reset"
                    round_msg_until = time.time() + 1.0
                elif event.key == pygame.K_s and rec is not None:
                    p = rec.save()
                    if p:
                        round_msg = f"saved {p}"
                        round_msg_until = time.time() + 2.0

        # ---------------- hand reading ----------------
        reading, cam_frame = ctrl.read()
        human_action = np.array([reading.steer, reading.throttle], dtype=np.float32)

        # ---------------- AI action ----------------
        # ai_obs is the cached pre-step view of the AI car (from env.reset() or
        # the previous step's return). One render per frame, not five.
        if active == "none" or policies[active] is None:
            ai_action = np.array([0.0, 0.4], dtype=np.float32)  # cruise
        else:
            ai_action = policies[active](ai_obs)

        # ---------------- recording (player POV pre-step) ----------------
        if rec is not None:
            human_obs = env._obs(env.opp, env.ego)
            rec.push(human_obs, reading.steer, reading.throttle)

        # step env: ego = AI, opp = human. Pass opp_action directly so env.step
        # skips the (otherwise wasted) opponent first-person render.
        ai_obs, reward, terminated, truncated, info = env.step(ai_action, opp_action=human_action)

        # ---------------- round-end logic ----------------
        round_done = (
            terminated or truncated or
            info["lap_ego"] >= LAPS_PER_ROUND or info["lap_opp"] >= LAPS_PER_ROUND
        )
        if round_done:
            round_msg = f"round {round_number} done - human laps={info['lap_opp']}, ai laps={info['lap_ego']}"
            round_msg_until = time.time() + 3.0
            round_number += 1

            # save recording into a fresh file so train_bc can pick it up
            if rec is not None:
                p = rec.save()
                rec = SessionRecorder(args.data_dir)
                if p:
                    print(f"[round] saved demo -> {p}")

            # kick off training (no-op if already running)
            if trainer is not None:
                started = trainer.maybe_start()
                if started:
                    print("[round] BC retraining started in background")

            ai_obs, _ = env.reset()

        # ---------------- hot-reload trained policy ----------------
        if trainer is not None and trainer.pending_reload:
            new_bc = load_bc_policy(args.bc)
            if new_bc is not None:
                policies["bc"] = new_bc
                if active == "none":
                    active = "bc"
                round_msg = "AI policy hot-reloaded"
                round_msg_until = time.time() + 2.0
            trainer.pending_reload = False

        # ---------------- render ----------------
        screen.fill((20, 20, 24))

        # spectator (top-down) on the left
        spec = env.render()
        spec_surface = pygame.surfarray.make_surface(np.transpose(spec, (1, 0, 2)))
        spec_surface = pygame.transform.scale(spec_surface, (SPECTATOR_PX, SPECTATOR_PX))
        screen.blit(spec_surface, (20, 20))

        # right column: player 3D nav cam (top), webcam (middle), AI camera (bottom)
        right_y = 20

        # 1) player 3D camera — the human's navigation view
        player_view = env.render_player_3d(H=240, W=320)
        player_surf = pygame.surfarray.make_surface(np.transpose(player_view, (1, 0, 2)))
        player_surf = fit_to_panel(player_surf, RIGHT_COL_W, 320)
        screen.blit(small_font.render("YOUR VIEW (3D nav camera)", True, (200, 200, 200)),
                    (RIGHT_COL_X, right_y))
        screen.blit(player_surf, (RIGHT_COL_X, right_y + 18))
        right_y += player_surf.get_height() + 18 + PANEL_GAP

        # 2) webcam with overlay
        if cam_frame is not None:
            overlaid = ctrl.overlay(cam_frame.copy(), reading)
            cam_surf = cv_to_pygame(overlaid)
            cam_surf = fit_to_panel(cam_surf, RIGHT_COL_W // 2 - 6, 160)
            screen.blit(small_font.render("hand (webcam)", True, (200, 200, 200)),
                        (RIGHT_COL_X, right_y))
            screen.blit(cam_surf, (RIGHT_COL_X, right_y + 18))

            # 3) AI camera preview — alongside the webcam
            ai_x = RIGHT_COL_X + RIGHT_COL_W // 2 + 6
            ai_surf = pygame.surfarray.make_surface(np.transpose(ai_obs, (1, 0, 2)))
            ai_surf = fit_to_panel(ai_surf, RIGHT_COL_W // 2 - 6, 160)
            screen.blit(small_font.render("AI camera (policy input)", True, (200, 200, 200)),
                        (ai_x, right_y))
            screen.blit(ai_surf, (ai_x, right_y + 18))

        # ---------------- HUD ----------------
        now = time.time()
        fps = 1.0 / max(1e-6, now - last_t)
        last_t = now
        train_status = trainer.status_line() if trainer else "(off)"
        hud_lines = [
            f"policy: {active.upper():4s}   fps: {fps:5.1f}   round: {round_number}",
            f"hand:   steer={reading.steer:+.2f}  throttle={reading.throttle:.2f}",
            f"ai:     steer={ai_action[0]:+.2f}  throttle={ai_action[1]:+.2f}",
            f"laps:   ai={info['lap_ego']}  human={info['lap_opp']}  (round = {LAPS_PER_ROUND} laps)",
            f"on track: {'yes' if not info['off_track'] else 'NO'}    collision: {info['collision']}",
            f"recording: {('on (' + str(len(rec)) + ')') if rec else 'off'}    auto-train: {train_status}",
            "[1]=BC  [2]=RL  [0]=cruise   [R]=reset   [S]=save   [Q]=quit",
        ]
        y = WINDOW_H - 20 * len(hud_lines) - 12
        for line in hud_lines:
            screen.blit(font.render(line, True, (220, 220, 220)), (20, y))
            y += 20

        # transient round message
        if round_msg and now < round_msg_until:
            big = pygame.font.SysFont("monospace", 28, bold=True)
            text = big.render(round_msg, True, (255, 230, 80))
            screen.blit(text, (20, 20 + SPECTATOR_PX + 12))

        pygame.display.flip()
        clock.tick(20)  # 20 Hz to match env.dt=0.05

    if rec is not None:
        out = rec.save()
        if out:
            print("recording saved to", out)
    ctrl.close()
    pygame.quit()


if __name__ == "__main__":
    main()
