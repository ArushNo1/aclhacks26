"""
Single CNN architecture used for behavioral cloning, PPO, and ONNX export.
One source of truth = no transfer-time mismatches.

Input: (B, 3, H, W) float32 in [0, 1].
Output: (B, 2) tanh-bounded actions (steer, throttle) in [-1, 1].
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import torch
import torch.nn as nn


DEFAULT_INPUT_SHAPE: Tuple[int, int, int] = (3, 120, 160)  # matches DeepRacer after resize


class PolicyCNN(nn.Module):
    def __init__(self, input_shape: Tuple[int, int, int] = DEFAULT_INPUT_SHAPE,
                 hidden: int = 256):
        super().__init__()
        c, h, w = input_shape
        self.input_shape = input_shape
        self.features = nn.Sequential(
            nn.Conv2d(c, 16, kernel_size=5, stride=2, padding=2), nn.ReLU(inplace=True),
            nn.Conv2d(16, 32, kernel_size=5, stride=2, padding=2), nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, stride=2, padding=1), nn.ReLU(inplace=True),
        )
        with torch.no_grad():
            dummy = torch.zeros(1, c, h, w)
            n_flat = self.features(dummy).reshape(1, -1).shape[1]
        self.head = nn.Sequential(
            nn.Linear(n_flat, hidden), nn.ReLU(inplace=True),
            nn.Linear(hidden, 2), nn.Tanh(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.features(x)
        z = z.reshape(z.size(0), -1)
        return self.head(z)


def preprocess_obs(obs_uint8: np.ndarray) -> torch.Tensor:
    """HxWx3 uint8 (or BxHxWx3) -> torch float tensor (B, 3, H, W) in [0, 1]."""
    if obs_uint8.ndim == 3:
        x = obs_uint8[None, ...]
    else:
        x = obs_uint8
    x = x.astype(np.float32) / 255.0
    x = np.transpose(x, (0, 3, 1, 2))
    return torch.from_numpy(x)


@torch.no_grad()
def policy_act(policy: PolicyCNN, obs_uint8: np.ndarray, device: str = "cpu") -> np.ndarray:
    """Convenience: HxWx3 uint8 -> (steer, throttle) numpy."""
    policy.eval()
    x = preprocess_obs(obs_uint8).to(device)
    a = policy(x).cpu().numpy()[0]
    return a
