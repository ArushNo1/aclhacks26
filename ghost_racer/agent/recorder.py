"""
Records (frame_uint8, steer, throttle) tuples to a compressed npz file.
Hooks in to play.py's main loop.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class Sample:
    frame: np.ndarray  # HxWx3 uint8
    steer: float
    throttle: float


class SessionRecorder:
    def __init__(self, out_dir: str = "ghost_racer/data"):
        os.makedirs(out_dir, exist_ok=True)
        self.out_dir = out_dir
        self._samples: List[Sample] = []
        self._started = time.time()

    def push(self, frame: np.ndarray, steer: float, throttle: float) -> None:
        self._samples.append(Sample(frame=frame.copy(), steer=float(steer), throttle=float(throttle)))

    def save(self) -> str:
        if not self._samples:
            return ""
        frames = np.stack([s.frame for s in self._samples], axis=0)
        actions = np.stack([[s.steer, s.throttle] for s in self._samples], axis=0).astype(np.float32)
        path = os.path.join(self.out_dir, f"session_{int(self._started)}.npz")
        np.savez_compressed(path, frames=frames, actions=actions)
        return path

    def __len__(self) -> int:
        return len(self._samples)
