"""
Webcam + MediaPipe Hands -> calibrated (steer, throttle).

Mapping
-------
- Steer: palm tilt (angle of the line from index-MCP (lm5) to pinky-MCP (lm17)),
  remapped through a per-user calibration (left/center/right) and then put
  through a quadratic curve so small tilts produce small steer (less twitchy).
- Throttle: hand openness (mean fingertip->MCP distance / palm width),
  remapped through a per-user calibration (closed-fist / open-hand).

Run standalone for live calibration + preview:
    python -m ghost_racer.control.hand_control --calibrate
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Optional, Tuple

import cv2
import numpy as np
import mediapipe as mp


SMOOTH_ALPHA = 0.35       # 0=no smoothing, 1=full inertia
STEER_EXPONENT = 2.0      # quadratic by default; increase for softer steering
DEFAULT_CALIB_PATH = "ghost_racer/data/hand_calibration.json"


# ------------------------------------------------------------------ calibration
@dataclass
class HandCalibration:
    """Per-user mapping from raw hand features to [-1, 1] axes."""
    center_tilt_rad: float = 0.0
    left_tilt_rad: float = -math.radians(40)
    right_tilt_rad: float = +math.radians(40)
    closed_openness: float = 0.5
    open_openness: float = 2.0
    steer_exponent: float = STEER_EXPONENT

    def map_steer(self, raw_tilt_rad: float) -> float:
        """
        Direction-agnostic mapping: regardless of whether L<C<R or L>C>R
        numerically, raw=L returns -1 and raw=R returns +1. This makes the
        calibration robust to mirror flips.
        """
        L = self.left_tilt_rad
        C = self.center_tilt_rad
        R = self.right_tilt_rad
        # is `raw` on the same side of center as L?
        if (raw_tilt_rad - C) * (L - C) >= 0:
            denom = L - C
            if abs(denom) < 1e-6:
                return 0.0
            s = -(raw_tilt_rad - C) / denom        # 0 at C, -1 at L
        else:
            denom = R - C
            if abs(denom) < 1e-6:
                return 0.0
            s = (raw_tilt_rad - C) / denom         # 0 at C, +1 at R
        s = max(-1.0, min(1.0, s))
        return math.copysign(abs(s) ** self.steer_exponent, s)

    def map_throttle(self, raw_openness: float) -> float:
        denom = (self.open_openness - self.closed_openness) or 1e-6
        t = (raw_openness - self.closed_openness) / denom
        return max(0.0, min(1.0, t))

    def save(self, path: str = DEFAULT_CALIB_PATH) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: str = DEFAULT_CALIB_PATH) -> "HandCalibration":
        if not os.path.exists(path):
            return cls()
        with open(path) as f:
            data = json.load(f)
        # tolerate older files missing fields
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class HandReading:
    steer: float = 0.0
    throttle: float = 0.0
    has_hand: bool = False
    raw_tilt_rad: float = 0.0
    raw_openness: float = 0.0


# ------------------------------------------------------------------ feature extraction
def _vec(a, b) -> Tuple[float, float]:
    return (b.x - a.x, b.y - a.y)


def _norm(v) -> float:
    return math.hypot(v[0], v[1])


def extract_raw(lms) -> Tuple[float, float]:
    """Returns (raw_tilt_rad, raw_openness) for one detected hand."""
    v = _vec(lms[5], lms[17])
    tilt = math.atan2(v[1], v[0])

    palm_width = _norm(_vec(lms[5], lms[17])) + 1e-6
    finger_lengths = [
        _norm(_vec(lms[5], lms[8])),
        _norm(_vec(lms[9], lms[12])),
        _norm(_vec(lms[13], lms[16])),
        _norm(_vec(lms[17], lms[20])),
    ]
    openness = (sum(finger_lengths) / 4.0) / palm_width
    return tilt, openness


def landmarks_to_action(lms, prev: HandReading, calib: HandCalibration) -> HandReading:
    raw_tilt, raw_open = extract_raw(lms)
    raw_steer = calib.map_steer(raw_tilt)
    raw_throttle = calib.map_throttle(raw_open)

    a = SMOOTH_ALPHA
    steer = a * prev.steer + (1 - a) * raw_steer
    throttle = a * prev.throttle + (1 - a) * raw_throttle

    return HandReading(
        steer=float(steer),
        throttle=float(throttle),
        has_hand=True,
        raw_tilt_rad=float(raw_tilt),
        raw_openness=float(raw_open),
    )


# ------------------------------------------------------------------ controller
class HandController:
    """Stateful wrapper over a webcam + MediaPipe Hands pipeline."""

    def __init__(self, cam_index: int = 0, mirror: bool = True,
                 calibration: Optional[HandCalibration] = None):
        self.cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera {cam_index}")
        self.mirror = mirror
        self.calibration = calibration or HandCalibration.load()
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
            self.last = landmarks_to_action(lms.landmark, self.last, self.calibration)
            self._draw.draw_landmarks(frame, lms, self._mp_hands.HAND_CONNECTIONS)
        else:
            a = SMOOTH_ALPHA
            self.last = HandReading(
                steer=a * self.last.steer,
                throttle=a * self.last.throttle,
                has_hand=False,
            )
        return self.last, frame

    def overlay(self, frame: np.ndarray, reading: HandReading) -> np.ndarray:
        """Draw steer/throttle bars + raw values on the webcam frame."""
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

    # --------------------------------------------------------------- calibration
    def run_calibration(self, window_name: str = "calibration",
                        save_path: str = DEFAULT_CALIB_PATH) -> HandCalibration:
        """
        Walks the user through 5 captures: center / left / right / closed / open.
        Each capture averages the raw value over ~0.5s once SPACE is pressed.
        Returns a saved HandCalibration.
        """
        steps = [
            ("center", "Hold hand level (palm flat). SPACE to capture.", "tilt"),
            ("left",   "Tilt hand FULLY LEFT. SPACE to capture.",        "tilt"),
            ("right",  "Tilt hand FULLY RIGHT. SPACE to capture.",       "tilt"),
            ("closed", "Make a fist. SPACE to capture.",                 "open"),
            ("open",   "Open hand wide, fingers extended. SPACE.",       "open"),
        ]
        captured: dict = {}

        for name, prompt, kind in steps:
            captured[name] = self._capture_step(window_name, prompt, kind)

        calib = HandCalibration(
            center_tilt_rad=captured["center"],
            left_tilt_rad=captured["left"],
            right_tilt_rad=captured["right"],
            closed_openness=captured["closed"],
            open_openness=captured["open"],
            steer_exponent=STEER_EXPONENT,
        )
        # No swap-if-reversed here: map_steer is direction-agnostic, and
        # map_throttle is a clean linear interp that works for either ordering.
        # Trusting the user's calibrated values preserves their left/right intent.
        calib.save(save_path)
        self.calibration = calib
        cv2.destroyWindow(window_name)
        return calib

    def _capture_step(self, window_name: str, prompt: str, kind: str) -> float:
        """Show prompt + live preview; on SPACE, average raw value over ~0.5s."""
        captured_value: Optional[float] = None
        capturing_until: Optional[float] = None
        samples: list = []

        while True:
            ok, frame = self.cap.read()
            if not ok:
                continue
            if self.mirror:
                frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            res = self._hands.process(rgb)

            raw_tilt = raw_open = None
            if res.multi_hand_landmarks:
                lms = res.multi_hand_landmarks[0]
                raw_tilt, raw_open = extract_raw(lms.landmark)
                self._draw.draw_landmarks(frame, lms, self._mp_hands.HAND_CONNECTIONS)

            now = time.time()
            if capturing_until is not None:
                if raw_tilt is not None:
                    samples.append(raw_tilt if kind == "tilt" else raw_open)
                if now >= capturing_until:
                    if samples:
                        captured_value = float(np.mean(samples))
                    capturing_until = None

            # overlay
            cv2.putText(frame, prompt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 255), 2, cv2.LINE_AA)
            if raw_tilt is not None:
                v = raw_tilt if kind == "tilt" else raw_open
                cv2.putText(frame, f"raw {kind}: {v:+.3f}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
            if capturing_until is not None:
                cv2.putText(frame, "CAPTURING...", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            if captured_value is not None:
                cv2.putText(frame, f"got {captured_value:+.3f} - SPACE to continue, R to redo",
                            (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1, cv2.LINE_AA)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                if captured_value is not None:
                    return captured_value
                if raw_tilt is not None and capturing_until is None:
                    samples = []
                    capturing_until = now + 0.5
            elif key == ord("r") and captured_value is not None:
                captured_value = None
                samples = []
                capturing_until = None
            elif key in (ord("q"), 27):  # q or ESC
                raise KeyboardInterrupt("calibration aborted")


# ------------------------------------------------------------------ standalone
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--calibrate", action="store_true",
                    help="Run calibration before showing the live preview.")
    args = ap.parse_args()

    try:
        ctrl = HandController(args.cam, mirror=not args.no_mirror)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    if args.calibrate:
        try:
            ctrl.run_calibration()
            print("calibration saved to", DEFAULT_CALIB_PATH)
        except KeyboardInterrupt:
            print("calibration aborted; using previous values")

    print("Press q to quit, c to recalibrate.")
    try:
        while True:
            reading, frame = ctrl.read()
            if frame is None:
                break
            frame = ctrl.overlay(frame, reading)
            cv2.imshow("hand control", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                cv2.destroyWindow("hand control")
                try:
                    ctrl.run_calibration()
                except KeyboardInterrupt:
                    pass
    finally:
        ctrl.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
