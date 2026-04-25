"""
Webcam + MediaPipe Hands -> (steer, throttle).

Mapping:
  - steer    in [-1, 1]: hand X position across the frame (left = -1, right = +1)
  - throttle in [-1, 1]: hand Y position (top = +1 forward, bottom = -1 reverse)
  - Pinch (thumb tip close to index tip) acts as a brake -> zeroes throttle.

Usage:
  python leap_hand_demo.py            # /dev/video0
  python leap_hand_demo.py --cam 2    # force /dev/video2
  python leap_hand_demo.py --mirror   # mirror horizontally (selfie view)
  q to quit.
"""

import argparse
import sys
import cv2
import numpy as np
import mediapipe as mp


def to_axes(landmarks, w: int, h: int):
    """Use the wrist (landmark 0) as the cursor; pinch (4 vs 8) as brake."""
    wrist = landmarks[0]
    thumb_tip = landmarks[4]
    index_tip = landmarks[8]

    steer = np.clip(2 * wrist.x - 1, -1, 1)
    throttle = np.clip(1 - 2 * wrist.y, -1, 1)

    dx = (thumb_tip.x - index_tip.x) * w
    dy = (thumb_tip.y - index_tip.y) * h
    pinch_norm = float(np.hypot(dx, dy)) / w
    braking = pinch_norm < 0.05

    if braking:
        throttle = 0.0

    return float(steer), float(throttle), braking


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0, help="V4L2 camera index (default: 0)")
    ap.add_argument("--mirror", action="store_true", help="Mirror the frame horizontally")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.cam, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"Could not open camera {args.cam}", file=sys.stderr)
        sys.exit(1)

    print(f"Using camera index {args.cam}. Press 'q' to quit.")

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    hands = mp_hands.Hands(
        model_complexity=0,
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

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

        steer, throttle, braking = 0.0, 0.0, False

        if result.multi_hand_landmarks:
            lms = result.multi_hand_landmarks[0]
            steer, throttle, braking = to_axes(lms.landmark, w, h)
            mp_draw.draw_landmarks(frame, lms, mp_hands.HAND_CONNECTIONS)

        bar_w = 200
        cx, cy = w // 2, h - 40
        cv2.rectangle(frame, (cx - bar_w, cy - 6), (cx + bar_w, cy + 6), (60, 60, 60), 1)
        cv2.circle(frame, (int(cx + steer * bar_w), cy), 8, (0, 255, 0), -1)

        ty0, ty1 = 40, h - 80
        tcx = w - 40
        cv2.rectangle(frame, (tcx - 6, ty0), (tcx + 6, ty1), (60, 60, 60), 1)
        ty = int(((1 - throttle) / 2) * (ty1 - ty0) + ty0)
        cv2.circle(frame, (tcx, ty), 8, (0, 165, 255), -1)

        label = f"steer={steer:+.2f}  throttle={throttle:+.2f}"
        if braking:
            label += "  [BRAKE]"
        cv2.putText(frame, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 0), 1, cv2.LINE_AA)

        cv2.imshow("hand control demo", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    hands.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
