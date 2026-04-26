"""Shared mutable state between the sim runner and the HTTP/WS handlers.

The runner mutates `SimState` once per env tick and publishes a snapshot to
all subscribed asyncio queues. WS handlers create one queue per client and
drain it forward to the browser.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional, Set


# Race phase signals what the dashboard should display globally.
#   idle      - sim running, no active race (engine on)
#   capture   - human is recording demonstrations
#   training  - BC retraining
#   race      - countdown lights then live race
Phase = str  # 'idle' | 'capture' | 'training' | 'race'

# Light phase inside a race. Mirrors the frontend's expectation in acts.tsx.
LightPhase = str  # 'off' | 'red' | 'yellow' | 'green'


@dataclass
class TrainingState:
    running: bool = False
    current_epoch: int = 0
    total_epochs: int = 200
    current_loss: float = 0.0
    loss_points: List[float] = field(default_factory=list)
    last_status: str = "idle"
    policy_version: Optional[str] = None  # e.g., "v3" (bump on reload)


@dataclass
class CaptureState:
    recording: bool = False
    session_id: Optional[str] = None
    started_at: Optional[float] = None
    frames: int = 0
    last_save_path: Optional[str] = None


@dataclass
class CarSnapshot:
    """Per-car snapshot in JSON-friendly form. car1 is the human slot
    (env.opp), car2 is the AI slot (env.ego)."""
    position_on_track: float = 0.0  # [0, 1] arc-length progress
    lap_count: int = 0
    lap_times: List[float] = field(default_factory=lambda: [0.0])  # cumulative race-clock seconds at each crossing
    last_lap_s: Optional[float] = None
    best_lap_s: Optional[float] = None
    speed: float = 0.0  # m/s


@dataclass
class RaceState:
    light_phase: LightPhase = "off"
    started: bool = False
    race_clock: float = 0.0
    car1: CarSnapshot = field(default_factory=CarSnapshot)
    car2: CarSnapshot = field(default_factory=CarSnapshot)
    off_track: bool = False
    collision: bool = False


@dataclass
class HandCalibrationStepView:
    """JSON-friendly view of the active calibration step (None when idle)."""
    index: int = 0
    total: int = 6
    target: str = ""        # 'L' | 'R'
    anchor: str = ""        # 'neutral' | 'forward' | 'backward'
    prompt: str = ""


@dataclass
class HandCalibrationState:
    active: bool = False
    step: Optional[HandCalibrationStepView] = None
    last_captured_size: Optional[float] = None
    error: Optional[str] = None
    completed: bool = False


@dataclass
class HandSnapshot:
    has_left: bool = False
    has_right: bool = False
    steer: float = 0.0
    throttle: float = 0.0
    raw_left_size: float = 0.0
    raw_right_size: float = 0.0
    attached: bool = False     # True when a webcam is attached and we have a HandCaptureRunner
    calibrated: bool = False   # True if a current-schema profile is loaded
    profile: Optional[Dict[str, float]] = None  # six anchor values, for display
    calibration: HandCalibrationState = field(default_factory=HandCalibrationState)


class SimState:
    """Owns the canonical snapshot. Mutated by SimRunner under a lock; read
    by HTTP handlers and WebSocket pumps."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.phase: Phase = "idle"
        self.race = RaceState()
        self.training = TrainingState()
        self.capture = CaptureState()
        self.hand = HandSnapshot()
        self.policy_active: str = "none"   # 'none' | 'bc' | 'rl' | 'human'
        self.policy_version: Optional[str] = None
        self.fps: float = 0.0
        self.tick: int = 0
        # Subscribers: per-client asyncio.Queue plus the loop they live on.
        self._subscribers: Set[asyncio.Queue[Dict[str, Any]]] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # --- subscription management (called from the asyncio side) ---

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> "asyncio.Queue[Dict[str, Any]]":
        q: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=8)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: "asyncio.Queue[Dict[str, Any]]") -> None:
        self._subscribers.discard(q)

    # --- mutation helpers (called from the sim thread or asyncio tick) ---

    def lock(self) -> Lock:
        return self._lock

    def snapshot(self) -> Dict[str, Any]:
        """Build a JSON-serializable snapshot of the current state."""
        with self._lock:
            return {
                "ts": time.time(),
                "tick": self.tick,
                "phase": self.phase,
                "fps": round(self.fps, 1),
                "policy_active": self.policy_active,
                "policy_version": self.policy_version,
                "race": {
                    "light_phase": self.race.light_phase,
                    "started": self.race.started,
                    "race_clock": round(self.race.race_clock, 2),
                    "off_track": self.race.off_track,
                    "collision": self.race.collision,
                    "car1": _car_dict(self.race.car1),
                    "car2": _car_dict(self.race.car2),
                },
                "hand": {
                    "has_left": self.hand.has_left,
                    "has_right": self.hand.has_right,
                    "steer": round(self.hand.steer, 4),
                    "throttle": round(self.hand.throttle, 4),
                    "raw_left_size": round(self.hand.raw_left_size, 4),
                    "raw_right_size": round(self.hand.raw_right_size, 4),
                    "attached": self.hand.attached,
                    "calibrated": self.hand.calibrated,
                    "profile": self.hand.profile,
                    "calibration": {
                        "active": self.hand.calibration.active,
                        "completed": self.hand.calibration.completed,
                        "error": self.hand.calibration.error,
                        "last_captured_size": (
                            round(self.hand.calibration.last_captured_size, 4)
                            if self.hand.calibration.last_captured_size is not None else None
                        ),
                        "step": (
                            None if self.hand.calibration.step is None else {
                                "index": self.hand.calibration.step.index,
                                "total": self.hand.calibration.step.total,
                                "target": self.hand.calibration.step.target,
                                "anchor": self.hand.calibration.step.anchor,
                                "prompt": self.hand.calibration.step.prompt,
                            }
                        ),
                    },
                },
                "training": {
                    "running": self.training.running,
                    "current_epoch": self.training.current_epoch,
                    "total_epochs": self.training.total_epochs,
                    "current_loss": round(self.training.current_loss, 5),
                    "loss_points": list(self.training.loss_points),
                    "last_status": self.training.last_status,
                    "policy_version": self.training.policy_version,
                },
                "capture": {
                    "recording": self.capture.recording,
                    "session_id": self.capture.session_id,
                    "started_at": self.capture.started_at,
                    "duration_s": (
                        time.time() - self.capture.started_at
                        if self.capture.started_at and self.capture.recording
                        else 0.0
                    ),
                    "frames": self.capture.frames,
                    "last_save_path": self.capture.last_save_path,
                },
            }

    def publish(self) -> None:
        """Push current snapshot to all subscribers. Safe to call from any
        thread (asyncio loop thread or otherwise) — the fan-out always runs
        on the loop thread via `call_soon_threadsafe`."""
        snapshot = self.snapshot()
        loop = self._loop
        if loop is None:
            return
        loop.call_soon_threadsafe(self._fanout, snapshot)

    def _fanout(self, snapshot: Dict[str, Any]) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(snapshot)
            except asyncio.QueueFull:
                # Drop the oldest in favor of the newest snapshot
                try:
                    _ = q.get_nowait()
                except Exception:
                    pass
                try:
                    q.put_nowait(snapshot)
                except Exception:
                    pass


def _car_dict(c: CarSnapshot) -> Dict[str, Any]:
    return {
        "position_on_track": round(c.position_on_track, 4),
        "lap_count": c.lap_count,
        "lap_times": list(c.lap_times),
        "last_lap_s": round(c.last_lap_s, 3) if c.last_lap_s is not None else None,
        "best_lap_s": round(c.best_lap_s, 3) if c.best_lap_s is not None else None,
        "speed": round(c.speed, 3),
    }
