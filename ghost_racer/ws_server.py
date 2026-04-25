"""
WebSocket server: streams the Ghost Racer sim to any connected browser at ~20 Hz.

Usage:
    cd /home/arush/aclhacks26
    python -m ghost_racer.ws_server

Each tick sends one JSON message:
    {
        "spectator":    "<base64 JPEG, 600×600 top-down view>",
        "ai_fp":        "<base64 JPEG, 160×120 AI first-person>",
        "hand_fp":      "<base64 JPEG, webcam frame or human sim FP>",
        "lap_ego":      int,
        "lap_opp":      int,
        "steer":        float,
        "throttle":     float,
        "has_hand":     bool,
        "off_track":    bool,
        "collision":    bool,
        "ego_progress": float,
        "opp_progress": float,
        "fps":          float,
        "policy":       str   ("BC" | "CRUISE")
    }
"""

from __future__ import annotations

import asyncio
import base64
import json
import time

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ghost_racer.control.hand_control import HandController
from ghost_racer.sim.env import GhostRacerEnv

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def encode_frame(arr: np.ndarray, quality: int = 75) -> str:
    """RGB uint8 HxWx3 numpy array → base64 JPEG string."""
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    _, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf.tobytes()).decode("ascii")


def encode_bgr_frame(bgr: np.ndarray, quality: int = 75) -> str:
    """BGR uint8 (raw cv2 frame) → base64 JPEG string."""
    _, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf.tobytes()).decode("ascii")


def load_bc_policy():
    """Returns a policy callable or None if no checkpoint found."""
    import os
    path = "ghost_racer/data/bc_policy.pt"
    if not os.path.exists(path):
        return None
    try:
        import torch
        from ghost_racer.agent.policy import PolicyCNN, policy_act
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        policy = PolicyCNN(input_shape=ckpt.get("input_shape", (3, 120, 160)))
        policy.load_state_dict(ckpt["state_dict"])
        policy.eval()
        print(f"[ws_server] loaded BC policy from {path}")
        return lambda obs: policy_act(policy, obs, device="cpu")
    except Exception as e:
        print(f"[ws_server] could not load BC policy ({e}); using cruise fallback")
        return None


@app.websocket("/ws")
async def ws_demo(ws: WebSocket):
    await ws.accept()
    print("[ws_server] client connected")

    loop = asyncio.get_event_loop()
    policy_fn = load_bc_policy()
    policy_label = "BC" if policy_fn else "CRUISE"

    try:
        ctrl: HandController | None = HandController(cam_index=0, mirror=True)
        print("[ws_server] camera opened")
    except RuntimeError as e:
        ctrl = None
        print(f"[ws_server] no camera ({e}); running sim without hand input")

    env = GhostRacerEnv(opponent_policy=None)
    env.reset()

    last_t = time.perf_counter()

    try:
        while True:
            tick_start = time.perf_counter()

            # Read hand (blocking I/O → thread executor); fall back to neutral if no camera
            if ctrl is not None:
                reading, cam_frame = await loop.run_in_executor(None, ctrl.read)
            else:
                from ghost_racer.control.hand_control import HandReading
                reading = HandReading(steer=0.0, throttle=0.5, has_hand=False)
                cam_frame = None
            human_action = np.array([reading.steer, reading.throttle], dtype=np.float32)

            # AI action
            if policy_fn is not None:
                ai_obs = env._obs(env.ego, env.opp)
                ai_action = np.asarray(policy_fn(ai_obs), dtype=np.float32)
            else:
                ai_action = np.array([0.0, 0.4], dtype=np.float32)

            # Step sim (human drives the opponent car)
            env.opponent_policy = lambda _obs, _a=human_action: _a
            _, _, terminated, truncated, info = env.step(ai_action)

            # Render frames
            spec_arr = env.render()                       # 600×600 RGB
            ai_fp_arr = env._obs(env.ego, env.opp)        # 120×160 RGB
            human_fp_arr = env._obs(env.opp, env.ego)     # 120×160 RGB

            # Encode: prefer real webcam frame for hand_fp slot
            spec_b64 = encode_frame(spec_arr)
            ai_fp_b64 = encode_frame(ai_fp_arr)
            if cam_frame is not None:
                hand_fp_b64 = encode_bgr_frame(cam_frame)
            else:
                hand_fp_b64 = encode_frame(human_fp_arr)

            now = time.perf_counter()
            fps = 1.0 / max(1e-6, now - last_t)
            last_t = now

            msg = {
                "spectator": spec_b64,
                "ai_fp": ai_fp_b64,
                "hand_fp": hand_fp_b64,
                "lap_ego": info["lap_ego"],
                "lap_opp": info["lap_opp"],
                "steer": round(float(reading.steer), 3),
                "throttle": round(float(reading.throttle), 3),
                "has_hand": bool(reading.has_hand),
                "off_track": bool(info["off_track"]),
                "collision": bool(info["collision"]),
                "ego_progress": round(float(info["ego_progress"]), 3),
                "opp_progress": round(float(info["opp_progress"]), 3),
                "fps": round(fps, 1),
                "policy": policy_label,
            }

            await ws.send_text(json.dumps(msg))

            if terminated or truncated:
                env.reset()

            # Pace to ~20 Hz
            elapsed = time.perf_counter() - tick_start
            await asyncio.sleep(max(0.0, 0.05 - elapsed))

    except WebSocketDisconnect:
        print("[ws_server] client disconnected")
    except Exception as e:
        print(f"[ws_server] error: {e}")
    finally:
        if ctrl is not None:
            ctrl.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
