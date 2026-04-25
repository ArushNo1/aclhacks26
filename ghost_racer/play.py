"""
Demo entry point: human (hand) drives one car, AI policy drives the other.

  python -m ghost_racer.play --agent none           # both human / free practice
  python -m ghost_racer.play --agent bc             # AI uses bc_policy.pt
  python -m ghost_racer.play --agent rl             # AI uses rl_policy.zip
  python -m ghost_racer.play --record               # also write training data

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
import time
from typing import Callable, Optional

import numpy as np
import pygame

from .agent.policy import PolicyCNN, policy_act
from .agent.recorder import SessionRecorder
from .control.hand_control import HandController
from .sim.env import GhostRacerEnv


WINDOW_W, WINDOW_H = 1100, 660
SPECTATOR_PX = 600
FP_PREVIEW_W, FP_PREVIEW_H = 320, 240


def load_bc_policy(path: str, device: str = "cpu"):
    if not os.path.exists(path):
        return None
    import torch
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=["none", "bc", "rl"], default="none")
    ap.add_argument("--bc", default="ghost_racer/data/bc_policy.pt")
    ap.add_argument("--rl", default="ghost_racer/data/rl_policy.zip")
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--no-mirror", action="store_true")
    args = ap.parse_args()

    # hand input
    try:
        ctrl = HandController(args.cam, mirror=not args.no_mirror)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    # AI policies (lazy)
    policies = {
        "bc": load_bc_policy(args.bc),
        "rl": load_rl_policy(args.rl),
        "none": None,
    }
    active = args.agent
    if policies.get(active) is None and active != "none":
        print(f"warning: no {active} policy at expected path; falling back to 'none'", file=sys.stderr)
        active = "none"

    # env: ego = AI car, opp = human; we drive the ego with `policies[active]` and
    # pass the human reading as the opponent action via env.opponent_policy.
    # Trick: easier to just drive both cars manually in the env without the opp
    # callback — we step both with the same env API.
    env = GhostRacerEnv(opponent_policy=None)
    obs, _ = env.reset()

    # pygame window
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Ghost Racer — hand vs clone")
    font = pygame.font.SysFont("monospace", 18)
    clock = pygame.time.Clock()

    rec: Optional[SessionRecorder] = SessionRecorder() if args.record else None

    last_t = time.time()
    running = True
    while running:
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
                    obs, _ = env.reset()
                elif event.key == pygame.K_s and rec is not None:
                    print("saved ->", rec.save())

        # human action via hand
        reading, cam_frame = ctrl.read()
        human_action = np.array([reading.steer, reading.throttle], dtype=np.float32)

        # AI action
        if active == "none" or policies[active] is None:
            ai_action = np.array([0.0, 0.4], dtype=np.float32)  # cruise
        else:
            # AI's observation = render from AI's car POV, with opponent = human car
            ai_obs = env._obs(env.ego, env.opp)
            ai_action = policies[active](ai_obs)

        # ego = AI, opp = human. env.step calls opponent_policy(opp_obs) for
        # the opp action; install a one-shot closure returning this frame's
        # human reading.
        env.opponent_policy = lambda _obs, _a=human_action: _a
        obs, reward, terminated, truncated, info = env.step(ai_action)

        # record (player frame, player action)
        if rec is not None:
            human_obs = env._obs(env.opp, env.ego)
            rec.push(human_obs, reading.steer, reading.throttle)

        # ----------------------- render
        screen.fill((20, 20, 24))

        # spectator view
        spec = env.render()
        spec_surface = pygame.surfarray.make_surface(np.transpose(spec, (1, 0, 2)))
        spec_surface = pygame.transform.scale(spec_surface, (SPECTATOR_PX, SPECTATOR_PX))
        screen.blit(spec_surface, (20, 20))

        # AI's first-person preview
        ai_fp = env._obs(env.ego, env.opp)
        ai_surf = pygame.surfarray.make_surface(np.transpose(ai_fp, (1, 0, 2)))
        ai_surf = pygame.transform.scale(ai_surf, (FP_PREVIEW_W, FP_PREVIEW_H))
        screen.blit(ai_surf, (640, 20))
        screen.blit(font.render("AI camera", True, (200, 200, 200)), (640, 0))

        # human's first-person preview
        human_fp = env._obs(env.opp, env.ego)
        human_surf = pygame.surfarray.make_surface(np.transpose(human_fp, (1, 0, 2)))
        human_surf = pygame.transform.scale(human_surf, (FP_PREVIEW_W, FP_PREVIEW_H))
        screen.blit(human_surf, (640, 280))
        screen.blit(font.render("human camera", True, (200, 200, 200)), (640, 260))

        # HUD
        now = time.time()
        fps = 1.0 / max(1e-6, now - last_t)
        last_t = now
        hud_lines = [
            f"policy: {active.upper():4s}   fps: {fps:5.1f}",
            f"hand:   steer={reading.steer:+.2f}  throttle={reading.throttle:.2f}",
            f"ai:     steer={ai_action[0]:+.2f}  throttle={ai_action[1]:+.2f}",
            f"laps:   ai={info['lap_ego']}  human={info['lap_opp']}",
            f"on track: {'yes' if not info['off_track'] else 'NO'}    collision: {info['collision']}",
            f"recording: {'on (' + str(len(rec)) + ' frames)' if rec else 'off'}",
            "[1]=BC  [2]=RL  [0]=cruise   [R]=reset   [S]=save   [Q]=quit",
        ]
        for i, line in enumerate(hud_lines):
            screen.blit(font.render(line, True, (220, 220, 220)), (20, 640 - 20 * (len(hud_lines) - i)))

        pygame.display.flip()
        clock.tick(20)  # 20 Hz to match env.dt=0.05

        if terminated or truncated:
            obs, _ = env.reset()

    if rec is not None:
        out = rec.save()
        if out:
            print("recording saved to", out)
    ctrl.close()
    pygame.quit()


if __name__ == "__main__":
    main()
