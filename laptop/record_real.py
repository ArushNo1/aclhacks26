#!/usr/bin/env python3
"""Record (camera frame, steer, throttle) tuples from the live DeepRacer
into the same .npz schema ghost_racer/agent/bc_train.py consumes.

Run alongside laptop/hand_drive.py:
  - hand_drive.py drives the car (publishes commands the user makes)
  - record_real.py listens to BOTH the camera frames and the commands and
    pairs them up, so the dataset reflects exactly what the policy will see
    at inference time with what the human commanded at that moment.

Schema match: each sample is (frame uint8 HxWx3 RGB at the policy's input
shape, steer float, throttle float). Output:
  ghost_racer/data/real/session_<unix_ts>.npz   with keys 'frames', 'actions'

Then train with the existing trainer, e.g.:
  python -m ghost_racer.agent.bc_train --data-dir ghost_racer/data/real

Env: CAR_ID, MQTT_BROKER, MQTT_PORT (same defaults as the other laptop tools).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np
import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ghost_racer.agent.policy import DEFAULT_INPUT_SHAPE   # (3, H, W)
from ghost_racer.agent.recorder import SessionRecorder

CAR_ID = os.environ.get("CAR_ID", "1")
BROKER = os.environ.get("MQTT_BROKER", "localhost")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
FRAME_TOPIC = f"car/{CAR_ID}/frame"
CMD_TOPIC = f"car/{CAR_ID}/cmd"


class Pairing:
    """Latest-command + frame-driven sample push. Thread-safe."""
    def __init__(self, recorder: SessionRecorder, target_hw: Tuple[int, int],
                 invert_throttle: bool, preview: bool):
        self.recorder = recorder
        self.target_hw = target_hw  # (H, W)
        self.invert_throttle = invert_throttle
        self.preview = preview
        self._lock = threading.Lock()
        self._latest_cmd: Optional[Tuple[float, float, float]] = None  # (steer, throttle, ts)
        self._latest_frame: Optional[np.ndarray] = None  # for preview
        self.frame_count = 0
        self.cmd_count = 0
        self.dropped_no_cmd = 0
        self.start_t = time.time()

    def on_cmd(self, payload: bytes) -> None:
        try:
            d = json.loads(payload)
            steer = float(d.get("steer", 0.0))
            throttle = float(d.get("throttle", 0.0))
        except Exception:
            return
        if self.invert_throttle:
            # hand_drive negates before publishing, so the topic carries the
            # car-wired sign. Undo that so the saved label is in sim/policy
            # convention (positive throttle = forward).
            throttle = -throttle
        with self._lock:
            self._latest_cmd = (steer, throttle, time.monotonic())
            self.cmd_count += 1

    def on_frame(self, payload: bytes) -> None:
        arr = np.frombuffer(payload, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            return
        H, W = self.target_hw
        small = cv2.resize(bgr, (W, H), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        with self._lock:
            cmd = self._latest_cmd
            self._latest_frame = bgr
        if cmd is None:
            self.dropped_no_cmd += 1
            return
        steer, throttle, _ = cmd
        self.recorder.push(rgb, steer, throttle)
        self.frame_count += 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="ghost_racer/data/real",
                    help="Output dir; matches what bc_train.py expects.")
    ap.add_argument("--no-invert-throttle", action="store_true",
                    help="Disable un-inverting throttle. Use only if hand_drive.py "
                         "is NOT negating throttle for the physical car.")
    ap.add_argument("--no-preview", action="store_true",
                    help="Don't show a preview window.")
    ap.add_argument("--save-every-s", type=float, default=0.0,
                    help="Auto-save a checkpoint every N seconds (0 = save only on quit).")
    args = ap.parse_args()

    _, H, W = DEFAULT_INPUT_SHAPE
    print(f"[rec] policy input shape: {H}x{W} (RGB)")
    rec = SessionRecorder(out_dir=args.out_dir)
    pairing = Pairing(rec, target_hw=(H, W),
                      invert_throttle=not args.no_invert_throttle,
                      preview=not args.no_preview)

    def on_msg(_client, _ud, msg):
        if msg.topic == FRAME_TOPIC:
            pairing.on_frame(msg.payload)
        elif msg.topic == CMD_TOPIC:
            pairing.on_cmd(msg.payload)

    client = mqtt.Client(client_id=f"recorder-{CAR_ID}")
    client.on_message = on_msg
    client.connect(BROKER, PORT, keepalive=60)
    client.subscribe([(FRAME_TOPIC, 0), (CMD_TOPIC, 0)])
    client.loop_start()

    print(f"[rec] subscribed: {FRAME_TOPIC}, {CMD_TOPIC}")
    print(f"[rec] writing to: {args.out_dir}/session_*.npz   (q in preview to stop)")

    last_log = time.time()
    last_save = time.time()
    try:
        while True:
            time.sleep(0.05)
            if pairing.preview:
                with pairing._lock:
                    f = pairing._latest_frame.copy() if pairing._latest_frame is not None else None
                if f is not None:
                    cv2.putText(f, f"samples={pairing.frame_count}  cmds={pairing.cmd_count}",
                                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (0, 255, 0), 1, cv2.LINE_AA)
                    cv2.imshow("recorder (BGR preview)", f)
                    if (cv2.waitKey(1) & 0xFF) == ord("q"):
                        break

            now = time.time()
            if now - last_log > 5.0:
                dt = now - pairing.start_t
                print(f"[rec] {pairing.frame_count} pairs in {dt:.1f}s "
                      f"({pairing.frame_count / max(dt, 1e-6):.1f}/s); "
                      f"cmds={pairing.cmd_count}, dropped(no-cmd-yet)={pairing.dropped_no_cmd}")
                last_log = now
            if args.save_every_s > 0 and now - last_save > args.save_every_s:
                p = rec.save()
                if p:
                    print(f"[rec] checkpoint -> {p} ({len(rec)} samples)")
                # rotate: start a fresh recorder so we don't re-save the same samples
                rec = SessionRecorder(out_dir=args.out_dir)
                pairing.recorder = rec
                last_save = now
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        client.loop_stop()
        client.disconnect()
        path = rec.save()
        if path:
            print(f"[rec] saved -> {path} ({len(rec)} samples)")
        else:
            print("[rec] no samples captured")


if __name__ == "__main__":
    main()
