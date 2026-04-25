"""
Behavioral cloning: regress (steer, throttle) from RGB frames.
Loads every session_*.npz under the data/ dir, MSE loss, saves bc_policy.pt.
"""

from __future__ import annotations

import argparse
import glob
import os
from typing import List

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split

from .policy import DEFAULT_INPUT_SHAPE, PolicyCNN, preprocess_obs


def load_sessions(data_dir: str) -> tuple:
    paths = sorted(glob.glob(os.path.join(data_dir, "session_*.npz")))
    if not paths:
        raise FileNotFoundError(f"No session_*.npz files in {data_dir}. Record some demos first.")
    frames_list: List[np.ndarray] = []
    actions_list: List[np.ndarray] = []
    for p in paths:
        d = np.load(p)
        frames_list.append(d["frames"])
        actions_list.append(d["actions"])
        print(f"  loaded {p}: {len(d['frames'])} samples")
    frames = np.concatenate(frames_list, axis=0)
    actions = np.concatenate(actions_list, axis=0)
    return frames, actions


def train_bc(data_dir: str, out_path: str, epochs: int = 10, batch: int = 64, lr: float = 1e-3,
             device: str = "cpu") -> None:
    frames, actions = load_sessions(data_dir)
    print(f"Total: {len(frames)} samples; action mean={actions.mean(0)}, std={actions.std(0)}")

    x = preprocess_obs(frames)               # (N, 3, H, W) float
    y = torch.from_numpy(actions).float()    # (N, 2)
    ds = TensorDataset(x, y)

    n_val = max(1, len(ds) // 10)
    n_train = len(ds) - n_val
    train_ds, val_ds = random_split(ds, [n_train, n_val], generator=torch.Generator().manual_seed(0))

    train_loader = DataLoader(train_ds, batch_size=batch, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch, shuffle=False)

    policy = PolicyCNN(input_shape=DEFAULT_INPUT_SHAPE).to(device)
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    for epoch in range(1, epochs + 1):
        policy.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            pred = policy(xb)
            loss = loss_fn(pred, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            train_loss += loss.item() * xb.size(0)
        train_loss /= n_train

        policy.eval()
        val_loss = 0.0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                pred = policy(xb)
                val_loss += loss_fn(pred, yb).item() * xb.size(0)
        val_loss /= n_val

        print(f"epoch {epoch:02d}  train_mse={train_loss:.4f}  val_mse={val_loss:.4f}")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    torch.save({"state_dict": policy.state_dict(), "input_shape": DEFAULT_INPUT_SHAPE}, out_path)
    print(f"saved -> {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ghost_racer/data")
    ap.add_argument("--out", default="ghost_racer/data/bc_policy.pt")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    train_bc(args.data_dir, args.out, epochs=args.epochs, device=args.device)


if __name__ == "__main__":
    main()
