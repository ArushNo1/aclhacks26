"""
Webcam + MediaPipe Hands -> calibrated (steer, throttle).

Mapping
-------
- Steer: arm rotation. At calibration we capture the wrist position at neutral
  and place a fixed PIVOT below it (approximating where the shoulder would be).
  At runtime, steer = atan2(wrist - pivot), remapped through the per-user
  left/center/right arm angles and shaped by a soft curve. Swinging your whole
  arm left/right rotates the (pivot -> wrist) vector around the fixed pivot.
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


SMOOTH_ALPHA = 0.10       # 0=no smoothing, 1=full inertia
STEER_EXPONENT = 3.0      # raise for softer center, lower for sharper
STEER_DEADZONE = 0.02     # raw-axis fraction treated as zero (kills jitter near center)
STEER_MAX = 0.15          # cap on |steer| output; hands can't reliably hit ±1
PIVOT_OFFSET_Y = 0.55     # in normalized image-height units; how far BELOW the
                          # neutral wrist the fixed pivot sits (~ where the
                          # shoulder is, off-frame). Bigger = arm motion needs
                          # to be larger to produce the same angle change.
DEFAULT_CALIB_PATH = "ghost_racer/data/hand_calibration.json"


def _wrap_pi(d: float) -> float:
    """Wrap an angle difference into (-pi, pi]."""
    return (d + math.pi) % (2 * math.pi) - math.pi


def arm_angle(wrist_xy: Tuple[float, float],
              pivot_xy: Tuple[float, float]) -> float:
    """Angle (rad) of the vector from pivot to wrist, in image coords
    (y grows downward). Hand directly above pivot -> -pi/2."""
    return math.atan2(wrist_xy[1] - pivot_xy[1], wrist_xy[0] - pivot_xy[0])


# ------------------------------------------------------------------ calibration
@dataclass
class HandCalibration:
    """Per-user mapping from arm-rotation features to [-1, 1] axes."""
    # fixed pivot in normalized image coords, captured at calibration
    pivot_x: float = 0.5
    pivot_y: float = 1.05  # below the frame
    # arm-vector angles at the three calibrated positions (radians)
    center_arm_rad: float = -math.pi / 2
    left_arm_rad: float = -math.pi / 2 - math.radians(30)
    right_arm_rad: float = -math.pi / 2 + math.radians(30)
    # throttle (unchanged)
    closed_openness: float = 0.5
    open_openness: float = 2.0
    steer_exponent: float = STEER_EXPONENT

    def map_steer(self, raw_arm_rad: float) -> float:
        """
        Map a raw arm angle to a steer in [-STEER_MAX, +STEER_MAX].

        Direction-agnostic: regardless of whether L<C<R or L>C>R numerically,
        raw=L returns -1 and raw=R returns +1. Angle differences are wrapped
        into (-pi, pi] so the mapping behaves correctly even when the
        calibrated angles straddle the discontinuity at +/-pi.
        """
        dr = _wrap_pi(raw_arm_rad - self.center_arm_rad)
        dL = _wrap_pi(self.left_arm_rad - self.center_arm_rad)
        dR = _wrap_pi(self.right_arm_rad - self.center_arm_rad)
        # same side of center as left?
        if dr * dL >= 0:
            denom = dL
            if abs(denom) < 1e-6:
                return 0.0
            s = -dr / denom
        else:
            denom = dR
            if abs(denom) < 1e-6:
                return 0.0
            s = dr / denom
        s = max(-1.0, min(1.0, s))
        # deadzone around center, then re-normalize so the rest of the range is smooth
        if abs(s) <= STEER_DEADZONE:
            return 0.0
        s = (abs(s) - STEER_DEADZONE) / (1.0 - STEER_DEADZONE) * (1.0 if s > 0 else -1.0)
        out = math.copysign(abs(s) ** STEER_EXPONENT, s)
        return max(-STEER_MAX, min(STEER_MAX, out))

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
            c = cls()
            c._has_arm_data = False  # type: ignore[attr-defined]
            return c
        with open(path) as f:
            data = json.load(f)
        # tolerate older files missing fields
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        c = cls(**valid)
        # tag whether the file was written under the arm-rotation schema
        c._has_arm_data = "pivot_x" in data and "center_arm_rad" in data  # type: ignore[attr-defined]
        return c

    @property
    def has_arm_data(self) -> bool:
        """True if this calibration was loaded from a file using the
        arm-rotation schema (pivot + arm angles)."""
        return getattr(self, "_has_arm_data", True)


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


def extract_raw(lms) -> Tuple[Tuple[float, float], float]:
    """Returns (wrist_xy_normalized, raw_openness) for one detected hand."""
    wrist_xy = (lms[0].x, lms[0].y)

    palm_width = _norm(_vec(lms[5], lms[17])) + 1e-6
    finger_lengths = [
        _norm(_vec(lms[5], lms[8])),
        _norm(_vec(lms[9], lms[12])),
        _norm(_vec(lms[13], lms[16])),
        _norm(_vec(lms[17], lms[20])),
    ]
    openness = (sum(finger_lengths) / 4.0) / palm_width
    return wrist_xy, openness


def landmarks_to_action(lms, prev: HandReading, calib: HandCalibration) -> HandReading:
    wrist_xy, raw_open = extract_raw(lms)
    raw_arm = arm_angle(wrist_xy, (calib.pivot_x, calib.pivot_y))
    raw_steer = calib.map_steer(raw_arm)
    raw_throttle = calib.map_throttle(raw_open)

    a = SMOOTH_ALPHA
    steer = a * prev.steer + (1 - a) * raw_steer
    throttle = a * prev.throttle + (1 - a) * raw_throttle

    return HandReading(
        steer=float(steer),
        throttle=float(throttle),
        has_hand=True,
        raw_tilt_rad=float(raw_arm),  # repurposed: now the arm angle
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
        self.last_wrist: Optional[Tuple[float, float]] = None

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
            self.last_wrist = (lms.landmark[0].x, lms.landmark[0].y)
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
        """Draw steer/throttle bars + arm-pivot indicator on the webcam frame."""
        h, w = frame.shape[:2]

        # arm pivot + arm vector
        c = self.calibration
        px = int(c.pivot_x * w)
        py = int(c.pivot_y * h)
        # pivot is usually below the frame; clip drawing to the bottom edge
        px_d = max(0, min(w - 1, px))
        py_d = max(0, min(h - 1, py))
        cv2.circle(frame, (px_d, py_d), 6, (0, 200, 255), -1)
        cv2.putText(frame, "pivot", (px_d + 8, py_d - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1, cv2.LINE_AA)
        if self.last_wrist is not None and reading.has_hand:
            wx = int(self.last_wrist[0] * w)
            wy = int(self.last_wrist[1] * h)
            cv2.line(frame, (px_d, py_d), (wx, wy), (0, 200, 255), 2)

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

        label = f"steer={reading.steer:+.2f}  throttle={reading.throttle:.2f}  arm={math.degrees(reading.raw_tilt_rad):+5.1f}deg"
        if not reading.has_hand:
            label += "  [NO HAND]"
        cv2.putText(frame, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 0), 1, cv2.LINE_AA)
        return frame

    def close(self) -> None:
        self._hands.close()
        self.cap.release()

    # --------------------------------------------------------------- startup prompt
    def prompt_use_saved(self, window_name: str = "hand profile",
                         calib_path: str = DEFAULT_CALIB_PATH,
                         timeout_s: float = 12.0) -> bool:
        """
        Show a popup asking whether to use the saved hand profile or recalibrate.
        Returns True to use saved, False to recalibrate.
        Auto-accepts saved profile after `timeout_s` of inactivity.
        """
        if not os.path.exists(calib_path):
            return False
        c = self.calibration
        deg = math.degrees
        info = [
            f"Saved hand profile found: {calib_path}",
            f"  pivot:       ({c.pivot_x:.2f}, {c.pivot_y:.2f}) (norm. img coords)",
            f"  center arm:  {deg(c.center_arm_rad):+6.1f} deg",
            f"  left arm:    {deg(c.left_arm_rad):+6.1f} deg",
            f"  right arm:   {deg(c.right_arm_rad):+6.1f} deg",
            f"  closed/open: {c.closed_openness:.2f} / {c.open_openness:.2f}",
        ]
        deadline = time.time() + timeout_s
        while True:
            ok, frame = self.cap.read()
            if not ok:
                # camera died; fall back to "use saved"
                return True
            if self.mirror:
                frame = cv2.flip(frame, 1)
            remaining = max(0.0, deadline - time.time())
            cv2.putText(frame, "Use saved hand profile?", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
            for i, line in enumerate(info):
                cv2.putText(frame, line, (10, 60 + i * 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
            cv2.putText(frame, f"[ENTER/Y] use saved ({remaining:0.0f}s)   [R/N] recalibrate   [Q] quit",
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
        Walks the user through 5 captures:
          1. neutral arm position  -> defines the fixed pivot
          2. arm swung fully left  -> left arm angle
          3. arm swung fully right -> right arm angle
          4. closed fist           -> throttle floor
          5. open hand             -> throttle ceiling

        Steer is the angle of the (pivot -> wrist) vector, so swinging your
        whole arm rotates it around the pivot like a steering wheel.
        """
        # 1) neutral: fixes the pivot
        center_wrist = self._capture_xy(
            window_name,
            "Hold arm at NEUTRAL (centered, comfortable resting). SPACE to capture.",
        )
        pivot = (center_wrist[0], center_wrist[1] + PIVOT_OFFSET_Y)
        center_arm = arm_angle(center_wrist, pivot)  # ~ -pi/2

        # 2) left
        left_wrist = self._capture_xy(
            window_name,
            "Swing arm FULLY LEFT (rotate from shoulder, keep grip). SPACE.",
            pivot=pivot,
        )
        left_arm = arm_angle(left_wrist, pivot)

        # 3) right
        right_wrist = self._capture_xy(
            window_name,
            "Swing arm FULLY RIGHT (rotate from shoulder, keep grip). SPACE.",
            pivot=pivot,
        )
        right_arm = arm_angle(right_wrist, pivot)

        # 4) closed-fist openness
        closed = self._capture_scalar(window_name, "Make a fist. SPACE to capture.")
        # 5) open-hand openness
        open_ = self._capture_scalar(window_name, "Open hand wide, fingers extended. SPACE.")

        calib = HandCalibration(
            pivot_x=pivot[0],
            pivot_y=pivot[1],
            center_arm_rad=center_arm,
            left_arm_rad=left_arm,
            right_arm_rad=right_arm,
            closed_openness=closed,
            open_openness=open_,
            steer_exponent=STEER_EXPONENT,
        )
        # map_steer is direction-agnostic, so L/R swap is handled automatically.
        calib.save(save_path)
        self.calibration = calib
        cv2.destroyWindow(window_name)
        return calib

    def _capture_xy(self, window_name: str, prompt: str,
                    pivot: Optional[Tuple[float, float]] = None
                    ) -> Tuple[float, float]:
        """
        Capture the mean wrist position over ~0.5s after SPACE. If `pivot` is
        provided, also visualizes the arm vector (pivot -> wrist) live.
        Returns (x, y) in normalized image coords.
        """
        captured: Optional[Tuple[float, float]] = None
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

            wrist_xy: Optional[Tuple[float, float]] = None
            if res.multi_hand_landmarks:
                lms = res.multi_hand_landmarks[0]
                wrist_xy = (lms.landmark[0].x, lms.landmark[0].y)
                self._draw.draw_landmarks(frame, lms, self._mp_hands.HAND_CONNECTIONS)

            now = time.time()
            if capturing_until is not None:
                if wrist_xy is not None:
                    samples.append(wrist_xy)
                if now >= capturing_until:
                    if samples:
                        xs = [s[0] for s in samples]
                        ys = [s[1] for s in samples]
                        captured = (float(np.mean(xs)), float(np.mean(ys)))
                    capturing_until = None

            # visualize pivot + arm vector (pivot is usually below the frame)
            if pivot is not None:
                px = int(pivot[0] * w)
                py = int(pivot[1] * h)
                px_d = max(0, min(w - 1, px))
                py_d = max(0, min(h - 1, py))
                cv2.circle(frame, (px_d, py_d), 6, (0, 200, 255), -1)
                if wrist_xy is not None:
                    wx = int(wrist_xy[0] * w)
                    wy = int(wrist_xy[1] * h)
                    cv2.line(frame, (px_d, py_d), (wx, wy), (0, 200, 255), 2)

            # overlay text
            cv2.putText(frame, prompt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 255), 2, cv2.LINE_AA)
            if wrist_xy is not None:
                tag = f"wrist: ({wrist_xy[0]:.2f}, {wrist_xy[1]:.2f})"
                if pivot is not None:
                    tag += f"  arm: {math.degrees(arm_angle(wrist_xy, pivot)):+6.1f} deg"
                cv2.putText(frame, tag, (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
            if capturing_until is not None:
                cv2.putText(frame, "CAPTURING...", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            if captured is not None:
                cv2.putText(frame,
                            f"got ({captured[0]:.2f}, {captured[1]:.2f}) - SPACE to continue, R to redo",
                            (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1, cv2.LINE_AA)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                if captured is not None:
                    return captured
                if wrist_xy is not None and capturing_until is None:
                    samples = []
                    capturing_until = now + 0.5
            elif key == ord("r") and captured is not None:
                captured = None
                samples = []
                capturing_until = None
            elif key in (ord("q"), 27):
                raise KeyboardInterrupt("calibration aborted")

    def _capture_scalar(self, window_name: str, prompt: str) -> float:
        """Capture mean openness over ~0.5s after SPACE."""
        captured: Optional[float] = None
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

            raw_open: Optional[float] = None
            if res.multi_hand_landmarks:
                lms = res.multi_hand_landmarks[0]
                _, raw_open = extract_raw(lms.landmark)
                self._draw.draw_landmarks(frame, lms, self._mp_hands.HAND_CONNECTIONS)

            now = time.time()
            if capturing_until is not None:
                if raw_open is not None:
                    samples.append(raw_open)
                if now >= capturing_until:
                    if samples:
                        captured = float(np.mean(samples))
                    capturing_until = None

            cv2.putText(frame, prompt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 255), 2, cv2.LINE_AA)
            if raw_open is not None:
                cv2.putText(frame, f"raw openness: {raw_open:+.3f}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
            if capturing_until is not None:
                cv2.putText(frame, "CAPTURING...", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            if captured is not None:
                cv2.putText(frame, f"got {captured:+.3f} - SPACE to continue, R to redo",
                            (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1, cv2.LINE_AA)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                if captured is not None:
                    return captured
                if raw_open is not None and capturing_until is None:
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
