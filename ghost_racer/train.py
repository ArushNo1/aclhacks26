"""
Top-level training CLI.

  python -m ghost_racer.train bc                       # train BC on data/session_*.npz
  python -m ghost_racer.train rl --bc <bc.pt>          # train PPO with BC opponent
  python -m ghost_racer.train bc+rl                    # both, in sequence
"""

from __future__ import annotations

import argparse
import os

import torch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["bc", "rl", "bc+rl"])
    ap.add_argument("--data-dir", default="ghost_racer/data")
    ap.add_argument("--bc-out", default="ghost_racer/data/bc_policy.pt")
    ap.add_argument("--rl-out", default="ghost_racer/data/rl_policy.zip")
    ap.add_argument("--bc-epochs", type=int, default=10)
    ap.add_argument("--rl-steps", type=int, default=200_000)
    ap.add_argument("--domain-rand", action="store_true")
    ap.add_argument("--n-envs", type=int, default=4)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"

    if args.mode in ("bc", "bc+rl"):
        from .agent.bc_train import train_bc
        train_bc(args.data_dir, args.bc_out, epochs=args.bc_epochs, device=device)

    if args.mode in ("rl", "bc+rl"):
        from .agent.rl_train import train as train_rl
        bc_path = args.bc_out if os.path.exists(args.bc_out) else None
        train_rl(bc_path, args.rl_out, total_steps=args.rl_steps,
                 domain_rand=args.domain_rand, n_envs=args.n_envs)


if __name__ == "__main__":
    main()
