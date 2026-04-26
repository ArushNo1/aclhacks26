#!/usr/bin/env python3
"""Webcam hand tracking -> MQTT car/{CAR_ID}/cmd -> live DeepRacer.

Pairs with car_bridge/command_subscriber.py running on the car. Wave a hand at
the webcam; the car mirrors it. Uses the same calibrated hand controls as
ghost_racer (arm-rotation steering, openness throttle).

Env: CAR_ID, MQTT_BROKER, MQTT_PORT (same as smoke_cmd.py / view_frames.py).
"""
import argparse
import json
import os
import sys
import time

import cv2
import numpy as np
import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ghost_racer.control.hand_control import (DEFAULT_CALIB_PATH,
                                              HandController)

CAR_ID = os.environ.get("CAR_ID", "1")
BROKER = os.environ.get("MQTT_BROKER", "localhost")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = f"car/{CAR_ID}/cmd"

NO_HAND_TIMEOUT_S = 0.5


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0, help="V4L2 camera index")
    ap.add_argument("--no-mirror", action="store_true",
                    help="Disable horizontal frame mirroring")
    ap.add_argument("--max-throttle", type=float, default=0.4,
                    help="Clamp |throttle| before publish (default 0.4 for safety)")
    ap.add_argument("--rate", type=float, default=20.0,
                    help="MQTT publish rate cap, Hz (default 20)")
    ap.add_argument("--calibrate", action="store_true",
                    help="Force recalibration on startup (skips the use-saved prompt).")
    ap.add_argument("--skip-calibrate", action="store_true",
                    help="Skip the startup prompt and always use the saved profile.")
    args = ap.parse_args()

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

    client = mqtt.Client(client_id=f"hand-{CAR_ID}")
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()

    def publish(steer: float, throttle: float) -> None:
        payload = json.dumps({"steer": float(steer), "throttle": float(float(np.clip(throttle, -args.max_throttle, args.max_throttle)))})
        client.publish(TOPIC, payload, qos=0)

    print(f"[drive] mqtt://{BROKER}:{PORT}/{TOPIC}  cap={args.max_throttle}  rate={args.rate}Hz")
    print("[drive] q to quit (sends a zero command on exit)")

    period = 1.0 / max(args.rate, 1.0)
    next_pub = 0.0
    last_hand_ts = 0.0

    try:
        while True:
            reading, frame = ctrl.read()
            if frame is None:
                print("Frame grab failed.", file=sys.stderr)
                break

            now = time.monotonic()
            if reading.has_hand:
                last_hand_ts = now

            stale = (now - last_hand_ts) > NO_HAND_TIMEOUT_S
            if not reading.has_hand and stale:
                steer, throttle = 0.0, 0.0
            else:
                steer, throttle = reading.steer, reading.throttle

            throttle_out = float(np.clip(throttle, -args.max_throttle, args.max_throttle))
            steer_out = float(np.clip(steer, -1.0, 1.0))

            if now >= next_pub:
                publish(steer_out, throttle_out)
                next_pub = now + period

            frame = ctrl.overlay(frame, reading)
            h = frame.shape[0]
            if not reading.has_hand and stale:
                cv2.putText(frame, "[NO HAND -> 0]", (10, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, f"mqtt://{BROKER}:{PORT}/{TOPIC}", (10, h - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

            cv2.imshow("hand drive", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                cv2.destroyWindow("hand drive")
                try:
                    ctrl.run_calibration()
                except KeyboardInterrupt:
                    pass
    except KeyboardInterrupt:
        pass
    finally:
        try:
            publish(0.0, 0.0)
            time.sleep(0.05)
        except Exception:
            pass
        ctrl.close()
        cv2.destroyAllWindows()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
