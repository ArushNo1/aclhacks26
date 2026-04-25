"""
Webcam + MediaPipe Hands -> (steer, throttle) using:
  - steer:    palm tilt (roll), measured as the angle of the line from the
              index-MCP (lm5) to the pinky-MCP (lm17). Hand level => steer = 0.
  - throttle: hand openness, measured as the mean distance from each fingertip
              (lm8, 12, 16, 20) to its MCP (lm5, 9, 13, 17), normalized by
              palm width (lm5 -> lm17). Closed fist = 0, open hand = 1.

Both are exponentially smoothed.

Run standalone for calibration:
    python -m ghost_racer.control.hand_control
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np
import mediapipe as mp


MAX_TILT_RAD = math.radians(40)   # tilt past which steer saturates to ±1
OPENNESS_CLOSED = 0.5             # ratio at full fist
OPENNESS_OPEN = 2.0               # ratio at fully open palm
SMOOTH_ALPHA = 0.35               # 0=no smoothing, 1=full inertia


@dataclass
class HandReading:
    steer: float = 0.0
    throttle: float = 0.0
    has_hand: bool = False
    raw_tilt_rad: float = 0.0
    raw_openness: float = 0.0


def _vec(a, b) -> Tuple[float, float]:
    return (b.x - a.x, b.y - a.y)


def _norm(v) -> float:
    return math.hypot(v[0], v[1])


def landmarks_to_action(lms, prev: HandReading) -> HandReading:
    """Pure function: 21 normalized landmarks -> smoothed (steer, throttle)."""
    # tilt: angle of vector lm5 -> lm17, measured from image +x axis
    v = _vec(lms[5], lms[17])
    tilt = math.atan2(v[1], v[0])  # image y grows down; tilting hand right -> positive
    raw_steer = max(-1.0, min(1.0, tilt / MAX_TILT_RAD))

    # openness: avg(fingertip->mcp) / palm_width
    palm_width = _norm(_vec(lms[5], lms[17])) + 1e-6
    finger_lengths = [
        _norm(_vec(lms[5], lms[8])),
        _norm(_vec(lms[9], lms[12])),
        _norm(_vec(lms[13], lms[16])),
        _norm(_vec(lms[17], lms[20])),
    ]
    openness_ratio = (sum(finger_lengths) / 4.0) / palm_width
    raw_throttle = (openness_ratio - OPENNESS_CLOSED) / (OPENNESS_OPEN - OPENNESS_CLOSED)
    raw_throttle = max(0.0, min(1.0, raw_throttle))

    # smooth
    a = SMOOTH_ALPHA
    steer = a * prev.steer + (1 - a) * raw_steer
    throttle = a * prev.throttle + (1 - a) * raw_throttle

    return HandReading(
        steer=float(steer),
        throttle=float(throttle),
        has_hand=True,
        raw_tilt_rad=float(tilt),
        raw_openness=float(openness_ratio),
    )


class HandController:
    """Stateful wrapper over a webcam + MediaPipe Hands pipeline."""

    def __init__(self, cam_index: int = 0, mirror: bool = True):
        self.cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera {cam_index}")
        self.mirror = mirror
        self._hands = mp.solutions.hands.Hands(
            model_complexity=0,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._draw = mp.solutions.drawing_utils
        self._mp_hands = mp.solutions.hands
        self.last = HandReading()

    def read(self) -> Tuple[HandReading, Optional[np.ndarray]]:
        ok, frame = self.cap.read()
        if not ok:
            return self.last, None
        if self.mirror:
            frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._hands.process(rgb)

        if result.multi_hand_landmarks:
            lms = result.multi_hand_landmarks[0]
            self.last = landmarks_to_action(lms.landmark, self.last)
            self._draw.draw_landmarks(frame, lms, self._mp_hands.HAND_CONNECTIONS)
        else:
            # decay to neutral when no hand seen
            a = SMOOTH_ALPHA
            self.last = HandReading(
                steer=a * self.last.steer,
                throttle=a * self.last.throttle,
                has_hand=False,
            )
        return self.last, frame

    def overlay(self, frame: np.ndarray, reading: HandReading) -> np.ndarray:
        """Draw steer/throttle bars on the webcam frame for debugging."""
        h, w = frame.shape[:2]
        # steering bar
        bar_w = 200
        cx, cy = w // 2, h - 40
        cv2.rectangle(frame, (cx - bar_w, cy - 6), (cx + bar_w, cy + 6), (60, 60, 60), 1)
        cv2.circle(frame, (int(cx + reading.steer * bar_w), cy), 8, (0, 255, 0), -1)

        # throttle bar (vertical)
        ty0, ty1 = 40, h - 80
        tcx = w - 40
        cv2.rectangle(frame, (tcx - 6, ty0), (tcx + 6, ty1), (60, 60, 60), 1)
        ty = int(ty1 - reading.throttle * (ty1 - ty0))
        cv2.circle(frame, (tcx, ty), 8, (0, 165, 255), -1)

        label = f"steer={reading.steer:+.2f}  throttle={reading.throttle:.2f}"
        if not reading.has_hand:
            label += "  [NO HAND]"
        cv2.putText(frame, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 0), 1, cv2.LINE_AA)
        return frame

    def close(self) -> None:
        self._hands.close()
        self.cap.release()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--no-mirror", action="store_true")
    args = ap.parse_args()

    try:
        ctrl = HandController(args.cam, mirror=not args.no_mirror)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    print("Press q to quit.")
    try:
        while True:
            reading, frame = ctrl.read()
            if frame is None:
                break
            frame = ctrl.overlay(frame, reading)
            cv2.imshow("hand control (tilt=steer, open=throttle)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        ctrl.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
