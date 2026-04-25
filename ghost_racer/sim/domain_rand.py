"""Domain randomization knobs for sim2real. Toggle with env(domain_rand=True)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

import numpy as np


@dataclass
class DomainRand:
    enabled: bool = False
    rng: np.random.Generator = field(default_factory=np.random.default_rng)

    track_color: Tuple[int, int, int] = (60, 60, 60)
    grass_color: Tuple[int, int, int] = (40, 110, 40)
    line_color: Tuple[int, int, int] = (240, 240, 240)
    brightness: float = 1.0
    camera_pitch_deg: float = 0.0  # for first-person camera tilt jitter

    def resample(self) -> None:
        if not self.enabled:
            self.track_color = (60, 60, 60)
            self.grass_color = (40, 110, 40)
            self.line_color = (240, 240, 240)
            self.brightness = 1.0
            self.camera_pitch_deg = 0.0
            return

        def jitter(c, amp=30):
            return tuple(int(np.clip(v + self.rng.integers(-amp, amp + 1), 0, 255)) for v in c)

        self.track_color = jitter((60, 60, 60))
        self.grass_color = jitter((40, 110, 40))
        self.line_color = jitter((240, 240, 240), amp=15)
        self.brightness = float(self.rng.uniform(0.7, 1.3))
        self.camera_pitch_deg = float(self.rng.uniform(-3.0, 3.0))
