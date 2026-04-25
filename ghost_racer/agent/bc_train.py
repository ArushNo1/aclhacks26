"""
Behavioral cloning: regress (steer, throttle) from RGB frames.
Loads every session_*.npz under the data/ dir, MSE loss, saves the best-val
checkpoint to bc_policy.pt (mitigates overfitting on small recordings).
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


def load_sessions(data_dir: str, verbose: bool = True) -> tuple:
    paths = sorted(glob.glob(os.path.join(data_dir, "session_*.npz")))
    if not paths:
        raise FileNotFoundError(f"No session_*.npz files in {data_dir}. Record some demos first.")
    frames_list: List[np.ndarray] = []
    actions_list: List[np.ndarray] = []
    for p in paths:
        d = np.load(p)
        frames_list.append(d["frames"])
        actions_list.append(d["actions"])
        if verbose:
            print(f"  loaded {p}: {len(d['frames'])} samples")
    frames = np.concatenate(frames_list, axis=0)
    actions = np.concatenate(actions_list, axis=0)
    return frames, actions


def train_bc(data_dir: str, out_path: str, epochs: int = 8, batch: int = 64,
             lr: float = 1e-3, device: str = "cpu", verbose: bool = True) -> float:
    """Returns best val MSE."""
    frames, actions = load_sessions(data_dir, verbose=verbose)
    if verbose:
        print(f"Total: {len(frames)} samples; action mean={actions.mean(0)}, std={actions.std(0)}")

    x = preprocess_obs(frames)
    y = torch.from_numpy(actions).float()
    ds = TensorDataset(x, y)

    n_val = max(1, len(ds) // 10)
    n_train = len(ds) - n_val
    train_ds, val_ds = random_split(ds, [n_train, n_val],
                                    generator=torch.Generator().manual_seed(0))

    train_loader = DataLoader(train_ds, batch_size=batch, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch, shuffle=False)

    policy = PolicyCNN(input_shape=DEFAULT_INPUT_SHAPE).to(device)
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    best_val = float("inf")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

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
                val_loss += loss_fn(policy(xb), yb).item() * xb.size(0)
        val_loss /= n_val

        is_best = val_loss < best_val
        if is_best:
            best_val = val_loss
            torch.save({"state_dict": policy.state_dict(), "input_shape": DEFAULT_INPUT_SHAPE},
                       out_path)

        if verbose:
            tag = "  *best*" if is_best else ""
            print(f"epoch {epoch:02d}  train_mse={train_loss:.4f}  val_mse={val_loss:.4f}{tag}")

    if verbose:
        print(f"saved best (val_mse={best_val:.4f}) -> {out_path}")
    return best_val


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ghost_racer/data")
    ap.add_argument("--out", default="ghost_racer/data/bc_policy.pt")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    train_bc(args.data_dir, args.out, epochs=args.epochs, device=args.device)


if __name__ == "__main__":
    main()
