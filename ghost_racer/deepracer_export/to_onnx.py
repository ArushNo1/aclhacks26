"""
Exports a trained policy to ONNX so the same artifact can run on a real
DeepRacer (onnxruntime on the car's Atom, or onnxruntime-gpu on a laptop
that does the inference and pushes commands over MQTT).

Two export modes:
  - bc:  loads bc_policy.pt (a PolicyCNN state_dict) and exports it directly.
  - rl:  loads an SB3 PPO zip and wraps the deterministic policy for ONNX.

Output:
  rl_policy.onnx  (or bc_policy.onnx)
  policy_info.json  describing input shape and action scaling

The on-car ROS node should:
  1. resize the camera frame to (H, W) from policy_info.json
  2. transpose to (C, H, W), divide by 255.0
  3. run onnxruntime
  4. clip output to [-1, 1] then multiply by max_steer_rad / max_throttle_mps
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import torch
import torch.nn as nn

from ..agent.policy import DEFAULT_INPUT_SHAPE, PolicyCNN
from ..sim.car import MAX_SPEED_MPS, MAX_STEER_RAD


class _SB3Wrapper(nn.Module):
    """Wraps an SB3 ActorCriticPolicy to expose deterministic actions only."""

    def __init__(self, sb3_policy):
        super().__init__()
        self.policy = sb3_policy

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        # SB3 expects already-batched obs in (B, C, H, W) for CnnPolicy after VecTransposeImage.
        # We pre-transpose at call time to keep the ONNX inputs identical to BC.
        return self.policy(obs, deterministic=True)[0]


def export_bc(ckpt_path: str, out_path: str) -> dict:
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    shape = ckpt.get("input_shape", DEFAULT_INPUT_SHAPE)
    policy = PolicyCNN(input_shape=shape)
    policy.load_state_dict(ckpt["state_dict"])
    policy.eval()
    dummy = torch.zeros(1, *shape, dtype=torch.float32)
    torch.onnx.export(
        policy, dummy, out_path,
        input_names=["obs"], output_names=["action"],
        dynamic_axes={"obs": {0: "batch"}, "action": {0: "batch"}},
        opset_version=17,
    )
    return {"input_shape": list(shape), "kind": "bc"}


def export_rl(ckpt_path: str, out_path: str) -> dict:
    from stable_baselines3 import PPO

    model = PPO.load(ckpt_path, device="cpu")
    # SB3 image obs are normalized internally; we replicate that here so the
    # ONNX forward expects raw float32 in [0, 1] like the BC export.
    sb3_policy = model.policy
    wrapper = _SB3Wrapper(sb3_policy).eval()

    obs_space = sb3_policy.observation_space
    if len(obs_space.shape) == 3 and obs_space.shape[-1] == 3:
        c, h, w = 3, obs_space.shape[0], obs_space.shape[1]
    else:
        c, h, w = obs_space.shape  # already CHW
    dummy = torch.zeros(1, c, h, w, dtype=torch.float32)

    torch.onnx.export(
        wrapper, dummy, out_path,
        input_names=["obs"], output_names=["action"],
        dynamic_axes={"obs": {0: "batch"}, "action": {0: "batch"}},
        opset_version=17,
    )
    return {"input_shape": [c, h, w], "kind": "rl"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["bc", "rl"], required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.mode == "bc":
        info = export_bc(args.ckpt, args.out)
    else:
        info = export_rl(args.ckpt, args.out)

    info.update({
        "max_steer_rad": MAX_STEER_RAD,
        "max_throttle_mps": MAX_SPEED_MPS,
        "expects_normalized_input": True,
        "note": "Resize cam frame to (H, W), transpose to (C, H, W), divide by 255.",
    })
    info_path = os.path.splitext(args.out)[0] + "_info.json"
    with open(info_path, "w") as f:
        json.dump(info, f, indent=2)
    print(f"wrote {args.out} and {info_path}")


if __name__ == "__main__":
    main()
