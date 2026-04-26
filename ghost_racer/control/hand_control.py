"""
Webcam + MediaPipe Hands -> calibrated (steer, throttle), two hands, TANK DRIVE.

Mapping
-------
Each hand independently controls its side of the vehicle (like a tracked
vehicle / skid steer). The vertical height of each hand drives that
side's throttle, measured as `1 - mean_y` of the 21 hand landmarks in
normalized image coords — higher on screen = more throttle.

- LEFT  hand height -> left-tread throttle  in [-1, +1]
- RIGHT hand height -> right-tread throttle in [-1, +1]

Both hands lifted = full forward.  Both lowered = full reverse.  One
hand high and the other neutral (or low) creates a differential, which
the env consumes as a steering input.

The legacy *_size field names are retained for backward compatibility
with the saved calibration JSON, the SimState wire format, and the
frontend dashboard — values now represent elevation, not hand diameter.

We translate the two side throttles into the (steer, throttle) action the
sim expects:

    throttle = (left + right) / 2
    steer    = soft_curve((left - right) / 2)

Sign convention matches `Car.step` (positive steer = turn RIGHT). Tank
intuition: left side faster than right tread => vehicle curves right.

The two hands are distinguished by their x-position in the (mirrored)
frame: the user's right hand sits on the right side of the screen
(higher x).

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
from dataclasses import asdict, dataclass
from typing import Optional, Tuple

import cv2
import numpy as np
import mediapipe as mp


SMOOTH_ALPHA = 0.10       # 0=no smoothing, 1=full inertia
STEER_EXPONENT = 3.0      # raise for softer center, lower for sharper
STEER_DEADZONE = 0.02     # |differential| below this is treated as 0
STEER_MAX = 0.15          # cap on |steer| output sent to Car.step
THROTTLE_DEADZONE = 0.10  # per-side; |throttle| below this collapses to 0
DEFAULT_CALIB_PATH = "ghost_racer/data/hand_calibration.json"


def _shape_steer(diff: float) -> float:
    """Apply deadzone + exponent + STEER_MAX cap to a normalized
    differential in [-1, 1]. Used to convert tank-drive (L-R)/2 into the
    steer scalar the env consumes."""
    s = max(-1.0, min(1.0, diff))
    if abs(s) <= STEER_DEADZONE:
        return 0.0
    s = (abs(s) - STEER_DEADZONE) / (1.0 - STEER_DEADZONE) * (1.0 if s > 0 else -1.0)
    out = math.copysign(abs(s) ** STEER_EXPONENT, s)
    return max(-STEER_MAX, min(STEER_MAX, out))


# ------------------------------------------------------------------ calibration
@dataclass
class HandCalibration:
    """Per-user hand-height anchors for tank-drive throttle, one set per
    hand. Stored values are elevations (`1 - mean_y`) in normalized image
    coords; higher on screen = larger value = forward throttle. Field
    names retain the historical *_size suffix for wire compatibility."""
    # left tread
    left_neutral_size: float = 0.50
    left_forward_size: float = 0.85   # hand lifted high
    left_backward_size: float = 0.15  # hand lowered
    # right tread
    right_neutral_size: float = 0.50
    right_forward_size: float = 0.85
    right_backward_size: float = 0.15
    steer_exponent: float = STEER_EXPONENT

    @staticmethod
    def _map_side(raw_size: float, neutral: float, forward: float, backward: float) -> float:
        """Map a single hand's elevation to side-throttle in [-1, +1].
        Direction-agnostic so forward/backward can sit on either side of
        neutral (forward is normally larger but we don't assume it)."""
        df = forward - neutral
        db = backward - neutral
        dr = raw_size - neutral
        if dr * df >= 0:  # toward forward
            if abs(df) < 1e-6:
                return 0.0
            t = max(0.0, min(1.0, dr / df))
        else:             # toward backward
            if abs(db) < 1e-6:
                return 0.0
            t = max(-1.0, min(0.0, -dr / db))
        if abs(t) < THROTTLE_DEADZONE:
            return 0.0
        sign = 1.0 if t > 0 else -1.0
        return sign * (abs(t) - THROTTLE_DEADZONE) / (1.0 - THROTTLE_DEADZONE)

    def left_throttle(self, raw_size: float) -> float:
        return self._map_side(raw_size, self.left_neutral_size,
                              self.left_forward_size, self.left_backward_size)

    def right_throttle(self, raw_size: float) -> float:
        return self._map_side(raw_size, self.right_neutral_size,
                              self.right_forward_size, self.right_backward_size)

    def tank_to_action(self, left_t: float, right_t: float) -> Tuple[float, float]:
        """Combine two side throttles into (steer, throttle).
        positive steer = turn right (matches Car.step convention)."""
        throttle = 0.5 * (left_t + right_t)
        # left tread faster than right -> vehicle curves to the RIGHT
        steer = _shape_steer(0.5 * (left_t - right_t))
        return float(steer), float(max(-1.0, min(1.0, throttle)))

    def save(self, path: str = DEFAULT_CALIB_PATH) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: str = DEFAULT_CALIB_PATH) -> "HandCalibration":
        if not os.path.exists(path):
            c = cls()
            c._has_arm_data = False  # type: ignore[attr-defined]
            return c
        with open(path) as f:
            data = json.load(f)
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        c = cls(**valid)
        # tag whether the file was written under the current depth-tank schema
        c._has_arm_data = (
            "left_neutral_size" in data and "right_neutral_size" in data
        )  # type: ignore[attr-defined]
        return c

    @property
    def has_arm_data(self) -> bool:
        """True if this calibration was loaded from a file using the
        current tank-drive schema. Name kept for backwards compatibility
        with play.py."""
        return getattr(self, "_has_arm_data", True)


@dataclass
class HandReading:
    steer: float = 0.0
    throttle: float = 0.0
    has_hand: bool = False     # True if at least one hand detected
    has_left: bool = False
    has_right: bool = False
    left_throttle: float = 0.0
    right_throttle: float = 0.0
    raw_left_size: float = 0.50
    raw_right_size: float = 0.50


# ------------------------------------------------------------------ feature extraction
def hand_height(lms) -> float:
    """Elevation (`1 - mean_y`) of the 21 hand landmarks in normalized
    image coords. Larger = higher on screen = hand lifted up."""
    ys = sum(lm.y for lm in lms) / len(lms)
    return float(max(0.0, min(1.0, 1.0 - ys)))


# Legacy alias: callers (incl. server hand_runner) still import this name.
hand_size = hand_height


def hand_center(lms) -> Tuple[float, float]:
    """Mean of the 21 hand landmarks in normalized image coords. Used for
    overlay placement of the hand-size indicator."""
    xs = sum(lm.x for lm in lms) / len(lms)
    ys = sum(lm.y for lm in lms) / len(lms)
    return float(xs), float(ys)


def landmarks_to_action(left_lms, right_lms,
                        prev: HandReading,
                        calib: HandCalibration) -> HandReading:
    """Combine left + right hand landmarks into a smoothed tank-drive
    HandReading. Either side may be None when that hand is missing; the
    missing side's throttle decays toward zero via the smoothing constant."""
    a = SMOOTH_ALPHA

    # left tread
    if left_lms is not None:
        raw_left_size = hand_size(left_lms)
        raw_left_t = calib.left_throttle(raw_left_size)
        has_left = True
    else:
        raw_left_size = prev.raw_left_size
        raw_left_t = 0.0  # decay missing side toward 0
        has_left = False
    left_t = a * prev.left_throttle + (1 - a) * raw_left_t

    # right tread
    if right_lms is not None:
        raw_right_size = hand_size(right_lms)
        raw_right_t = calib.right_throttle(raw_right_size)
        has_right = True
    else:
        raw_right_size = prev.raw_right_size
        raw_right_t = 0.0
        has_right = False
    right_t = a * prev.right_throttle + (1 - a) * raw_right_t

    steer, throttle = calib.tank_to_action(left_t, right_t)

    return HandReading(
        steer=steer,
        throttle=throttle,
        has_hand=(has_left or has_right),
        has_left=has_left,
        has_right=has_right,
        left_throttle=float(left_t),
        right_throttle=float(right_t),
        raw_left_size=float(raw_left_size),
        raw_right_size=float(raw_right_size),
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
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._draw = mp.solutions.drawing_utils
        self._mp_hands = mp.solutions.hands
        self.last = HandReading()
        self.last_left_wrist: Optional[Tuple[float, float]] = None
        self.last_right_wrist: Optional[Tuple[float, float]] = None
        self.last_left_center: Optional[Tuple[float, float]] = None
        self.last_right_center: Optional[Tuple[float, float]] = None

    @staticmethod
    def _split_hands(hand_landmarks_list):
        """Sort hands by wrist x in the mirrored frame: lowest x = LEFT
        hand, highest x = RIGHT hand. With one hand visible, x >= 0.5
        routes it to the right slot."""
        if not hand_landmarks_list:
            return None, None
        if len(hand_landmarks_list) == 1:
            lms = hand_landmarks_list[0]
            wx = lms.landmark[0].x
            if wx >= 0.5:
                return None, lms
            return lms, None
        sorted_hands = sorted(hand_landmarks_list, key=lambda h: h.landmark[0].x)
        return sorted_hands[0], sorted_hands[-1]

    def read(self) -> Tuple[HandReading, Optional[np.ndarray]]:
        ok, frame = self.cap.read()
        if not ok:
            return self.last, None
        if self.mirror:
            frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._hands.process(rgb)

        left_lms, right_lms = self._split_hands(result.multi_hand_landmarks or [])
        if left_lms is not None or right_lms is not None:
            self.last = landmarks_to_action(
                left_lms.landmark if left_lms is not None else None,
                right_lms.landmark if right_lms is not None else None,
                self.last, self.calibration,
            )
            self.last_left_wrist = (
                (left_lms.landmark[0].x, left_lms.landmark[0].y)
                if left_lms is not None else None
            )
            self.last_right_wrist = (
                (right_lms.landmark[0].x, right_lms.landmark[0].y)
                if right_lms is not None else None
            )
            self.last_left_center = (
                hand_center(left_lms.landmark) if left_lms is not None else None
            )
            self.last_right_center = (
                hand_center(right_lms.landmark) if right_lms is not None else None
            )
            for lms in (left_lms, right_lms):
                if lms is not None:
                    self._draw.draw_landmarks(frame, lms, self._mp_hands.HAND_CONNECTIONS)
        else:
            a = SMOOTH_ALPHA
            self.last = HandReading(
                steer=a * self.last.steer,
                throttle=a * self.last.throttle,
                has_hand=False,
                left_throttle=a * self.last.left_throttle,
                right_throttle=a * self.last.right_throttle,
                raw_left_size=self.last.raw_left_size,
                raw_right_size=self.last.raw_right_size,
            )
            self.last_left_wrist = None
            self.last_right_wrist = None
            self.last_left_center = None
            self.last_right_center = None
        return self.last, frame

    def overlay(self, frame: np.ndarray, reading: HandReading) -> np.ndarray:
        """Draw per-side height guides + summary steer/throttle bars.
        Each side of the frame gets horizontal reference lines at the
        calibrated forward (green, high) and backward (blue, low)
        elevations, plus a live marker at the detected hand centroid."""
        h, w = frame.shape[:2]
        c = self.calibration

        def elev_to_y(elev: float) -> int:
            return int(max(0.0, min(1.0, 1.0 - elev)) * h)

        def draw_side(label: str, color,
                      neutral: float, forward: float, backward: float,
                      center: Optional[Tuple[float, float]],
                      live_elev: float, side_throttle: float,
                      x0: int, x1: int):
            y_fwd = elev_to_y(forward)
            y_back = elev_to_y(backward)
            y_neu = elev_to_y(neutral)
            cv2.line(frame, (x0, y_fwd), (x1, y_fwd), (60, 220, 60), 1, cv2.LINE_AA)
            cv2.line(frame, (x0, y_back), (x1, y_back), (60, 60, 220), 1, cv2.LINE_AA)
            cv2.line(frame, (x0, y_neu), (x1, y_neu), (140, 140, 140), 1, cv2.LINE_AA)
            cv2.putText(frame, f"{label} fwd", (x0 + 4, y_fwd - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 220, 60), 1, cv2.LINE_AA)
            cv2.putText(frame, f"{label} rev", (x0 + 4, y_back + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 60, 220), 1, cv2.LINE_AA)
            if center is not None:
                cx_px = int(center[0] * w)
                cy_px = int(center[1] * h)
                cv2.circle(frame, (cx_px, cy_px), 8, color, -1, cv2.LINE_AA)
                cv2.putText(frame, f"{label}  h={live_elev:.2f}  t={side_throttle:+.2f}",
                            (cx_px - 70, cy_px - 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

        draw_side("L", (0, 200, 255),
                  c.left_neutral_size, c.left_forward_size, c.left_backward_size,
                  self.last_left_center, reading.raw_left_size, reading.left_throttle,
                  0, w // 2)
        draw_side("R", (60, 220, 60),
                  c.right_neutral_size, c.right_forward_size, c.right_backward_size,
                  self.last_right_center, reading.raw_right_size, reading.right_throttle,
                  w // 2, w)

        # legend in the top-right
        cv2.putText(frame, "green = lift hand UP (fwd)", (w - 240, h - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 220, 60), 1, cv2.LINE_AA)
        cv2.putText(frame, "blue  = drop hand DOWN (rev)", (w - 240, h - 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 60, 220), 1, cv2.LINE_AA)

        # summary bars (steer horizontal at bottom, throttle vertical right-of-center)
        bar_w = 200
        cx, cy = w // 2, h - 40
        cv2.rectangle(frame, (cx - bar_w, cy - 6), (cx + bar_w, cy + 6),
                      (60, 60, 60), 1)
        cv2.circle(frame, (int(cx + reading.steer / max(STEER_MAX, 1e-6) * bar_w), cy),
                   8, (0, 255, 0), -1)

        ty0, ty1 = h - 240, h - 80
        tcx = cx + bar_w + 30
        mid = (ty0 + ty1) // 2
        cv2.rectangle(frame, (tcx - 6, ty0), (tcx + 6, ty1), (60, 60, 60), 1)
        cv2.line(frame, (tcx - 10, mid), (tcx + 10, mid), (180, 180, 180), 1)
        bar_half = (ty1 - ty0) // 2
        ty = int(mid - reading.throttle * bar_half)
        thr_color = (60, 220, 60) if reading.throttle >= 0 else (60, 60, 220)
        cv2.circle(frame, (tcx, ty), 8, thr_color, -1)

        flags = []
        if not reading.has_left:
            flags.append("NO L")
        if not reading.has_right:
            flags.append("NO R")
        flag_str = ("  [" + ", ".join(flags) + "]") if flags else ""
        label = (f"L={reading.left_throttle:+.2f}  R={reading.right_throttle:+.2f}  "
                 f"steer={reading.steer:+.2f}  thr={reading.throttle:+.2f}{flag_str}")
        cv2.putText(frame, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 255, 0), 1, cv2.LINE_AA)
        return frame

    def close(self) -> None:
        self._hands.close()
        self.cap.release()

    # --------------------------------------------------------------- startup prompt
    def prompt_use_saved(self, window_name: str = "hand profile",
                         calib_path: str = DEFAULT_CALIB_PATH,
                         timeout_s: float = 12.0) -> bool:
        """Popup asking whether to reuse the saved tank-drive profile or
        recalibrate. Returns True for use-saved."""
        if not os.path.exists(calib_path):
            return False
        c = self.calibration
        info = [
            f"Saved hand profile found: {calib_path}",
            f"  L hand height: neutral={c.left_neutral_size:.2f}  "
            f"fwd={c.left_forward_size:.2f}  rev={c.left_backward_size:.2f}",
            f"  R hand height: neutral={c.right_neutral_size:.2f}  "
            f"fwd={c.right_forward_size:.2f}  rev={c.right_backward_size:.2f}",
        ]
        deadline = time.time() + timeout_s
        while True:
            ok, frame = self.cap.read()
            if not ok:
                return True
            if self.mirror:
                frame = cv2.flip(frame, 1)
            remaining = max(0.0, deadline - time.time())
            cv2.putText(frame, "Use saved hand profile?", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
            for i, line in enumerate(info):
                cv2.putText(frame, line, (10, 60 + i * 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
            cv2.putText(frame,
                        f"[ENTER/Y] use saved ({remaining:0.0f}s)   [R/N] recalibrate   [Q] quit",
                        (10, frame.shape[0] - 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1, cv2.LINE_AA)
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("\r"), ord("\n"), 13, ord("y"), ord(" ")):
                cv2.destroyWindow(window_name)
                return True
            if key in (ord("r"), ord("n")):
                cv2.destroyWindow(window_name)
                return False
            if key in (ord("q"), 27):
                cv2.destroyWindow(window_name)
                raise KeyboardInterrupt("startup aborted")
            if remaining <= 0.0:
                cv2.destroyWindow(window_name)
                return True

    # --------------------------------------------------------------- calibration
    def run_calibration(self, window_name: str = "calibration",
                        save_path: str = DEFAULT_CALIB_PATH) -> HandCalibration:
        """
        Six captures (one hand at a time so detection is unambiguous):

          LEFT TREAD (left hand)
            1. neutral resting height
            2. lift hand UP (full L forward)
            3. drop hand DOWN (full L reverse)
          RIGHT TREAD (right hand)
            4. neutral resting height
            5. lift hand UP (full R forward)
            6. drop hand DOWN (full R reverse)
        """
        ln = self._capture_size(window_name,
                                "LEFT HAND only: hold at COMFORTABLE resting height. SPACE.")
        lf = self._capture_size(window_name,
                                "LEFT HAND only: lift hand UP (full L forward). SPACE.",
                                ref_size=ln)
        lb = self._capture_size(window_name,
                                "LEFT HAND only: drop hand DOWN (full L reverse). SPACE.",
                                ref_size=ln)

        rn = self._capture_size(window_name,
                                "RIGHT HAND only: hold at COMFORTABLE resting height. SPACE.")
        rf = self._capture_size(window_name,
                                "RIGHT HAND only: lift hand UP (full R forward). SPACE.",
                                ref_size=rn)
        rb = self._capture_size(window_name,
                                "RIGHT HAND only: drop hand DOWN (full R reverse). SPACE.",
                                ref_size=rn)

        calib = HandCalibration(
            left_neutral_size=ln, left_forward_size=lf, left_backward_size=lb,
            right_neutral_size=rn, right_forward_size=rf, right_backward_size=rb,
            steer_exponent=STEER_EXPONENT,
        )
        # _map_side is direction-agnostic, so close/far swaps are absorbed.
        calib.save(save_path)
        self.calibration = calib
        cv2.destroyWindow(window_name)
        return calib

    def _capture_size(self, window_name: str, prompt: str,
                      ref_size: Optional[float] = None) -> float:
        """Capture mean hand elevation over ~0.5s after SPACE. Optionally
        draws a faint horizontal reference line at `ref_size` (the
        previously captured neutral elevation) so the user can see how far
        above/below it their hand currently sits."""
        captured: Optional[float] = None
        capturing_until: Optional[float] = None
        samples: list = []

        while True:
            ok, frame = self.cap.read()
            if not ok:
                continue
            if self.mirror:
                frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            res = self._hands.process(rgb)

            sz: Optional[float] = None
            cx_px = cy_px = None
            if res.multi_hand_landmarks:
                lms = res.multi_hand_landmarks[0]
                sz = hand_height(lms.landmark)
                cx_n, cy_n = hand_center(lms.landmark)
                cx_px, cy_px = int(cx_n * w), int(cy_n * h)
                self._draw.draw_landmarks(frame, lms, self._mp_hands.HAND_CONNECTIONS)

            now = time.time()
            if capturing_until is not None:
                if sz is not None:
                    samples.append(sz)
                if now >= capturing_until:
                    if samples:
                        captured = float(np.mean(samples))
                    capturing_until = None

            if ref_size is not None:
                ref_y = int(max(0.0, min(1.0, 1.0 - ref_size)) * h)
                cv2.line(frame, (0, ref_y), (w, ref_y),
                         (180, 180, 180), 1, cv2.LINE_AA)
                cv2.putText(frame, "neutral", (8, max(12, ref_y - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                            (180, 180, 180), 1, cv2.LINE_AA)
            if cx_px is not None:
                cv2.circle(frame, (cx_px, cy_px), 8, (0, 220, 220), -1, cv2.LINE_AA)

            cv2.putText(frame, prompt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 255), 2, cv2.LINE_AA)
            if sz is not None:
                cv2.putText(frame, f"hand height: {sz:.3f}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
            if capturing_until is not None:
                cv2.putText(frame, "CAPTURING...", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            if captured is not None:
                cv2.putText(frame, f"got {captured:.3f} - SPACE to continue, R to redo",
                            (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1, cv2.LINE_AA)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                if captured is not None:
                    return captured
                if sz is not None and capturing_until is None:
                    samples = []
                    capturing_until = now + 0.5
            elif key == ord("r") and captured is not None:
                captured = None
                samples = []
                capturing_until = None
            elif key in (ord("q"), 27):
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
