"""Webcam + MediaPipe loop, step-driven calibration state machine, and
MJPEG-friendly overlay frame cache. Reuses ghost_racer.control.hand_control's
HandController for all the math; the only new thing is exposing the flow
to a browser instead of a cv2 popup window.

A background thread continuously reads frames at the camera's native rate,
runs MediaPipe Hands, and updates:
  - last_reading: smoothed HandReading consumed by SimRunner each tick
  - last_overlay_frame: BGR uint8 frame ready for JPEG encoding
  - per-side ring buffer of recent hand_size values used for calibration
    captures

Calibration is exposed as 6 ordered steps (LH neutral/close/far, RH
neutral/close/far). Browser drives via REST: start, capture, redo, cancel.
On capture we average the last ~0.5 s of samples for the targeted hand,
commit to a working HandCalibration, and advance. After step 6 we save
to disk and swap the new profile onto the controller.
"""
from __future__ import annotations

import copy
import dataclasses
import os
import threading
import time
from collections import deque
from dataclasses import asdict
from typing import Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np


# Local imports kept inside methods so the module loads cheaply at import
# time (mediapipe pulls heavy native deps).


CAM_INDEX_DEFAULT = int(os.environ.get("GHOST_RACER_CAM", "0"))


# ---------------------------------------------------------------- step plan
# Order must match HandController.run_calibration so saved profiles look the
# same across the cv2 and browser flows.
STEP_PLAN: List[Tuple[str, str, str]] = [
    ("L", "neutral",  "LEFT HAND only: hold at COMFORTABLE neutral distance, then press CAPTURE."),
    ("L", "forward",  "LEFT HAND only: push CLOSE to camera (full L forward), then press CAPTURE."),
    ("L", "backward", "LEFT HAND only: pull FAR from camera (full L reverse), then press CAPTURE."),
    ("R", "neutral",  "RIGHT HAND only: hold at COMFORTABLE neutral distance, then press CAPTURE."),
    ("R", "forward",  "RIGHT HAND only: push CLOSE to camera (full R forward), then press CAPTURE."),
    ("R", "backward", "RIGHT HAND only: pull FAR from camera (full R reverse), then press CAPTURE."),
]


class HandCaptureRunner:
    """Owns the webcam loop and the calibration state machine. Started by
    the FastAPI lifespan; stopped on shutdown."""

    def __init__(self, sim_state, cam_index: int = CAM_INDEX_DEFAULT,
                 mirror: bool = True) -> None:
        self.sim_state = sim_state
        self.cam_index = cam_index
        self.mirror = mirror
        # Filled in by start()
        self.controller = None        # HandController instance
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.attached: bool = False
        self.error: Optional[str] = None

        self._lock = threading.Lock()
        # Latest HandReading from controller (used by SimRunner.hand_action_provider)
        self.last_reading = None
        self.last_overlay_frame: Optional[np.ndarray] = None  # BGR

        # Per-side ring buffer of (hand_size, ts) for calibration captures
        # Using a deque so older samples drop off naturally.
        self._left_samples: "Deque[Tuple[float, float]]" = deque(maxlen=64)
        self._right_samples: "Deque[Tuple[float, float]]" = deque(maxlen=64)

        # Calibration state. Mutated under _lock.
        self._cal_active = False
        self._cal_step = 0
        self._cal_working = None  # HandCalibration (a copy, mutated step by step)
        self._cal_pre_snapshot = None  # original HandCalibration to restore on cancel
        self._cal_completed = False
        self._cal_error: Optional[str] = None
        self._cal_last_captured: Optional[float] = None

    # ----------------------------------------------------------- lifecycle
    def start(self) -> bool:
        """Try to attach the webcam + MediaPipe. Returns True on success.
        On failure stores the reason in `self.error` and leaves attached=False."""
        try:
            from ..control.hand_control import HandController
            self.controller = HandController(self.cam_index, mirror=self.mirror)
        except Exception as e:
            self.error = str(e)
            self.attached = False
            with self.sim_state.lock():
                self.sim_state.hand.attached = False
            print(f"[hand_runner] webcam unavailable: {e}")
            return False

        self.attached = True
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="hand-capture", daemon=True
        )
        self._thread.start()
        with self.sim_state.lock():
            self.sim_state.hand.attached = True
            self.sim_state.hand.calibrated = bool(
                self.controller.calibration.has_arm_data
            )
            self.sim_state.hand.profile = self._profile_view()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self.controller is not None:
            try:
                self.controller.close()
            except Exception:
                pass

    # ------------------------------------------------------------ thread
    def _loop(self) -> None:
        """Read frames continuously, update last_reading + overlay + ring buffers."""
        from ..control.hand_control import hand_size, hand_center  # noqa: WPS433

        while not self._stop.is_set():
            try:
                reading, frame = self.controller.read()
            except Exception as e:
                print(f"[hand_runner] read failed: {e}")
                time.sleep(0.05)
                continue
            if frame is None:
                time.sleep(0.02)
                continue

            # Pull the per-hand sizes from the latest MediaPipe result that the
            # controller already cached on `last_left_wrist`/`last_right_wrist`.
            # We need the live size, not the smoothed reading, so we recompute
            # from the latest landmarks via controller's sub-cache. The
            # controller already populated last_*_wrist; if we want the size
            # we'd need it cached too. The simplest way: re-extract by checking
            # `reading.raw_left_size` / `reading.raw_right_size` which the
            # controller keeps fresh.
            ts = time.monotonic()
            if reading.has_left:
                self._left_samples.append((float(reading.raw_left_size), ts))
            if reading.has_right:
                self._right_samples.append((float(reading.raw_right_size), ts))

            overlaid = self.controller.overlay(frame.copy(), reading)
            with self._lock:
                self.last_reading = reading
                self.last_overlay_frame = overlaid

            # Mirror live reading + presence into SimState for the dashboard
            with self.sim_state.lock():
                h = self.sim_state.hand
                h.has_left = reading.has_left
                h.has_right = reading.has_right
                h.steer = float(reading.steer)
                h.throttle = float(reading.throttle)
                h.raw_left_size = float(reading.raw_left_size)
                h.raw_right_size = float(reading.raw_right_size)
                h.calibrated = bool(self.controller.calibration.has_arm_data)
                h.profile = self._profile_view()
                self._publish_calibration_to_state()

            # Aim for ~30 fps; the camera FPS will gate us.
            time.sleep(0.02)

    # ------------------------------------------------------ calibration API
    def start_calibration(self) -> Dict[str, object]:
        from ..control.hand_control import HandCalibration  # noqa: WPS433
        with self._lock:
            self._cal_active = True
            self._cal_completed = False
            self._cal_step = 0
            self._cal_pre_snapshot = copy.deepcopy(self.controller.calibration)
            # Working copy starts from defaults so old anchors don't leak in
            # when the user is fully recalibrating.
            self._cal_working = HandCalibration()
            self._cal_error = None
            self._cal_last_captured = None
        return self._calibration_dict()

    def cancel_calibration(self) -> Dict[str, object]:
        with self._lock:
            if self._cal_pre_snapshot is not None:
                self.controller.calibration = self._cal_pre_snapshot
            self._cal_active = False
            self._cal_completed = False
            self._cal_step = 0
            self._cal_working = None
            self._cal_pre_snapshot = None
            self._cal_error = None
        return self._calibration_dict()

    def redo_step(self) -> Dict[str, object]:
        with self._lock:
            if not self._cal_active:
                return {"error": "calibration not active"}
            self._cal_error = None
            self._cal_last_captured = None
        return self._calibration_dict()

    def capture_step(self, window_s: float = 0.5,
                     min_samples: int = 4) -> Dict[str, object]:
        """Snapshot the targeted hand size and advance to the next step.

        Pulls samples from the per-hand ring buffer, restricted to the last
        `window_s` seconds. Errors if the user hasn't been showing the
        targeted hand long enough.
        """
        with self._lock:
            if not self._cal_active or self._cal_working is None:
                return {"error": "calibration not active"}
            if self._cal_step >= len(STEP_PLAN):
                return {"error": "calibration already complete"}
            target, anchor, _prompt = STEP_PLAN[self._cal_step]
            buf = self._left_samples if target == "L" else self._right_samples
            cutoff = time.monotonic() - window_s
            recent = [v for (v, t) in buf if t >= cutoff]
            if len(recent) < min_samples:
                self._cal_error = (
                    f"need {min_samples} samples of the {target} hand in the "
                    f"last {window_s}s, only got {len(recent)} (is the right hand visible?)"
                )
                return self._calibration_dict()
            value = float(np.mean(recent))
            # Commit to working calibration
            attr = _attr_for(target, anchor)
            setattr(self._cal_working, attr, value)
            self._cal_last_captured = value
            self._cal_error = None
            self._cal_step += 1

            if self._cal_step >= len(STEP_PLAN):
                # Persist + swap onto controller
                try:
                    self._cal_working.save()
                    self.controller.calibration = self._cal_working
                    self._cal_completed = True
                    self._cal_active = False
                    self._cal_pre_snapshot = None
                except Exception as e:
                    self._cal_error = f"save failed: {e}"
                    self._cal_completed = False
                    # leave active so user can retry the final commit
        return self._calibration_dict()

    def reset_calibration(self) -> Dict[str, object]:
        """Clear any saved profile (delete the JSON file). The controller
        drops back to defaults; the next start_calibration starts fresh."""
        from ..control.hand_control import (  # noqa: WPS433
            DEFAULT_CALIB_PATH,
            HandCalibration,
        )
        try:
            if os.path.exists(DEFAULT_CALIB_PATH):
                os.remove(DEFAULT_CALIB_PATH)
        except Exception as e:
            return {"error": f"failed to remove profile: {e}"}
        with self._lock:
            self.controller.calibration = HandCalibration()
            self._cal_active = False
            self._cal_completed = False
            self._cal_step = 0
            self._cal_working = None
            self._cal_pre_snapshot = None
        return self._calibration_dict()

    # ----------------------------------------------------------- helpers
    def _calibration_dict(self) -> Dict[str, object]:
        if self._cal_active and self._cal_step < len(STEP_PLAN):
            t, a, p = STEP_PLAN[self._cal_step]
            step = {
                "index": self._cal_step + 1,
                "total": len(STEP_PLAN),
                "target": t,
                "anchor": a,
                "prompt": p,
            }
        else:
            step = None
        return {
            "active": self._cal_active,
            "completed": self._cal_completed,
            "error": self._cal_error,
            "last_captured_size": self._cal_last_captured,
            "step": step,
        }

    def _publish_calibration_to_state(self) -> None:
        """Mirror the calibration dict into SimState (called under sim_state.lock())."""
        from .state import HandCalibrationState, HandCalibrationStepView
        d = self._calibration_dict()
        cal_state = HandCalibrationState(
            active=bool(d["active"]),
            completed=bool(d["completed"]),
            error=d["error"] if isinstance(d["error"], (str, type(None))) else None,
            last_captured_size=(
                float(d["last_captured_size"])
                if isinstance(d["last_captured_size"], (int, float)) else None
            ),
        )
        if d["step"] is not None:
            s = d["step"]
            cal_state.step = HandCalibrationStepView(
                index=int(s["index"]),
                total=int(s["total"]),
                target=str(s["target"]),
                anchor=str(s["anchor"]),
                prompt=str(s["prompt"]),
            )
        self.sim_state.hand.calibration = cal_state

    def _profile_view(self) -> Optional[Dict[str, float]]:
        c = self.controller.calibration
        if not c.has_arm_data:
            return None
        return {
            "left_neutral_size": float(c.left_neutral_size),
            "left_forward_size": float(c.left_forward_size),
            "left_backward_size": float(c.left_backward_size),
            "right_neutral_size": float(c.right_neutral_size),
            "right_forward_size": float(c.right_forward_size),
            "right_backward_size": float(c.right_backward_size),
        }


def _attr_for(target: str, anchor: str) -> str:
    side = "left" if target == "L" else "right"
    return f"{side}_{anchor}_size"
