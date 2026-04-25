"""
PPO fine-tune. The opponent in the env is a frozen behavioral-cloning policy
of the player, so the RL agent learns to overtake "someone who drives like
the player." This is what implements the "AI learns from the player's
movements" objective.

Usage:
    python -m ghost_racer.agent.rl_train --bc ghost_racer/data/bc_policy.pt \
        --steps 200000 --out ghost_racer/data/rl_policy.zip
"""

from __future__ import annotations

import argparse
import os
from typing import Optional

import numpy as np
import torch

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.vec_env import DummyVecEnv

from ..sim.env import GhostRacerEnv
from .policy import PolicyCNN, policy_act


def make_bc_opponent(bc_path: Optional[str], device: str = "cpu"):
    """Returns a callable obs -> action implementing the BC policy, or None."""
    if not bc_path or not os.path.exists(bc_path):
        return None
    ckpt = torch.load(bc_path, map_location=device, weights_only=False)
    policy = PolicyCNN(input_shape=ckpt.get("input_shape", (3, 120, 160))).to(device)
    policy.load_state_dict(ckpt["state_dict"])
    policy.eval()

    def opponent(obs: np.ndarray) -> np.ndarray:
        return policy_act(policy, obs, device=device)

    return opponent


def make_env_factory(bc_path: Optional[str], domain_rand: bool):
    def _factory():
        opp = make_bc_opponent(bc_path)
        return GhostRacerEnv(opponent_policy=opp, domain_rand=domain_rand)
    return _factory


def train(bc_path: Optional[str], out_path: str, total_steps: int,
          domain_rand: bool, n_envs: int = 4, log_dir: str = "ghost_racer/data/tb"):
    factory = make_env_factory(bc_path, domain_rand)
    vec = DummyVecEnv([factory for _ in range(n_envs)])

    model = PPO(
        "CnnPolicy",
        vec,
        verbose=1,
        n_steps=256,
        batch_size=256,
        learning_rate=3e-4,
        ent_coef=0.01,
        tensorboard_log=log_dir,
    )

    ckpt = CheckpointCallback(save_freq=max(1, total_steps // (10 * n_envs)),
                              save_path=os.path.dirname(out_path) or ".",
                              name_prefix="rl_ckpt")
    model.learn(total_timesteps=total_steps, callback=ckpt)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    model.save(out_path)
    print(f"saved -> {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bc", default="ghost_racer/data/bc_policy.pt",
                    help="BC checkpoint to use as the opponent (frozen).")
    ap.add_argument("--out", default="ghost_racer/data/rl_policy.zip")
    ap.add_argument("--steps", type=int, default=200_000)
    ap.add_argument("--domain-rand", action="store_true")
    ap.add_argument("--n-envs", type=int, default=4)
    args = ap.parse_args()

    train(args.bc, args.out, total_steps=args.steps,
          domain_rand=args.domain_rand, n_envs=args.n_envs)


if __name__ == "__main__":
    main()
