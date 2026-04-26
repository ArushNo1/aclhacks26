#!/usr/bin/env python3
"""Webcam hand tracking -> MQTT car/{CAR_ID}/cmd -> live DeepRacer.

Pairs with car_bridge/command_subscriber.py running on the car. Wave a hand at
the webcam; the car mirrors it.

Env: CAR_ID, MQTT_BROKER, MQTT_PORT (same as smoke_cmd.py / view_frames.py).
"""
import argparse
import json
import os
import sys
import time

import cv2
import mediapipe as mp
import numpy as np
import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from leap_demo.leap_hand_demo import to_axes

CAR_ID = os.environ.get("CAR_ID", "1")
BROKER = os.environ.get("MQTT_BROKER", "localhost")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = f"car/{CAR_ID}/cmd"

NO_HAND_TIMEOUT_S = 0.5


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0, help="V4L2 camera index")
    ap.add_argument("--mirror", action="store_true", help="Mirror frame horizontally")
    ap.add_argument("--max-throttle", type=float, default=0.4,
                    help="Clamp |throttle| before publish (default 0.4 for safety)")
    ap.add_argument("--rate", type=float, default=20.0,
                    help="MQTT publish rate cap, Hz (default 20)")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.cam, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"Could not open camera {args.cam}", file=sys.stderr)
        sys.exit(1)

    client = mqtt.Client(client_id=f"hand-{CAR_ID}")
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()

    def publish(steer: float, throttle: float) -> None:
        payload = json.dumps({"steer": float(steer), "throttle": float(throttle)})
        client.publish(TOPIC, payload, qos=0)

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    hands = mp_hands.Hands(
        model_complexity=0,
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    print(f"[drive] mqtt://{BROKER}:{PORT}/{TOPIC}  cap={args.max_throttle}  rate={args.rate}Hz")
    print("[drive] q to quit (sends a zero command on exit)")

    period = 1.0 / max(args.rate, 1.0)
    next_pub = 0.0
    last_hand_ts = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Frame grab failed.", file=sys.stderr)
                break

            if args.mirror:
                frame = cv2.flip(frame, 1)

            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            result = hands.process(rgb)

            now = time.monotonic()
            steer, throttle, braking = 0.0, 0.0, False
            hand_seen = False

            if result.multi_hand_landmarks:
                lms = result.multi_hand_landmarks[0]
                steer, throttle, braking = to_axes(lms.landmark, w, h)
                mp_draw.draw_landmarks(frame, lms, mp_hands.HAND_CONNECTIONS)
                hand_seen = True
                last_hand_ts = now

            stale = (now - last_hand_ts) > NO_HAND_TIMEOUT_S
            if not hand_seen and stale:
                steer, throttle = 0.0, 0.0

            throttle_out = float(np.clip(throttle, -args.max_throttle, args.max_throttle))
            steer_out = float(np.clip(steer, -1.0, 1.0))

            if now >= next_pub:
                publish(steer_out, throttle_out)
                next_pub = now + period

            bar_w = 200
            cx, cy = w // 2, h - 40
            cv2.rectangle(frame, (cx - bar_w, cy - 6), (cx + bar_w, cy + 6), (60, 60, 60), 1)
            cv2.circle(frame, (int(cx + steer_out * bar_w), cy), 8, (0, 255, 0), -1)

            ty0, ty1 = 40, h - 80
            tcx = w - 40
            cv2.rectangle(frame, (tcx - 6, ty0), (tcx + 6, ty1), (60, 60, 60), 1)
            ty = int(((1 - throttle_out / max(args.max_throttle, 1e-6)) / 2) * (ty1 - ty0) + ty0)
            cv2.circle(frame, (tcx, ty), 8, (0, 165, 255), -1)

            label = f"steer={steer_out:+.2f}  throttle={throttle_out:+.2f}"
            if braking:
                label += "  [BRAKE]"
            if not hand_seen and stale:
                label += "  [NO HAND -> 0]"
            cv2.putText(frame, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 0), 1, cv2.LINE_AA)
            cv2.putText(frame, f"mqtt://{BROKER}:{PORT}/{TOPIC}", (10, h - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

            cv2.imshow("hand drive", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        try:
            publish(0.0, 0.0)
            time.sleep(0.05)
        except Exception:
            pass
        hands.close()
        cap.release()
        cv2.destroyAllWindows()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
