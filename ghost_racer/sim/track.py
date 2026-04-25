"""Oval track in world coordinates (meters). Two straights joined by two semicircles.

Top-down layout, +x right, +y up. Start/finish line is at x=0 on the bottom
straight, with the cars heading in the +x direction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class Track:
    straight_length: float = 8.0   # meters, length of each straight
    centerline_radius: float = 3.0 # meters, radius of the centerline arc at each end
    track_width: float = 1.2       # meters, drivable corridor width

    def __post_init__(self):
        self.waypoints: np.ndarray = self._build_waypoints(n_per_segment=64)
        self._cum_lengths: np.ndarray = self._compute_cum_lengths(self.waypoints)
        self.total_length: float = float(self._cum_lengths[-1])

    # ------------------------------------------------------------------ geometry
    def _build_waypoints(self, n_per_segment: int) -> np.ndarray:
        """Centerline waypoints, ordered counter-clockwise starting at (0, -R)."""
        L = self.straight_length
        R = self.centerline_radius
        pts: List[Tuple[float, float]] = []

        # bottom straight: from (-L/2, -R) to (+L/2, -R)
        for i in range(n_per_segment):
            t = i / n_per_segment
            x = -L / 2 + t * L
            pts.append((x, -R))

        # right semicircle: from (+L/2, -R) around to (+L/2, +R), center at (+L/2, 0)
        for i in range(n_per_segment):
            theta = -math.pi / 2 + (i / n_per_segment) * math.pi
            x = L / 2 + R * math.cos(theta)
            y = R * math.sin(theta)
            pts.append((x, y))

        # top straight: from (+L/2, +R) to (-L/2, +R)
        for i in range(n_per_segment):
            t = i / n_per_segment
            x = L / 2 - t * L
            pts.append((x, R))

        # left semicircle: from (-L/2, +R) around to (-L/2, -R), center at (-L/2, 0)
        for i in range(n_per_segment):
            theta = math.pi / 2 + (i / n_per_segment) * math.pi
            x = -L / 2 + R * math.cos(theta)
            y = R * math.sin(theta)
            pts.append((x, y))

        return np.asarray(pts, dtype=np.float32)

    @staticmethod
    def _compute_cum_lengths(wp: np.ndarray) -> np.ndarray:
        deltas = np.diff(np.vstack([wp, wp[:1]]), axis=0)
        seg = np.linalg.norm(deltas, axis=1)
        return np.concatenate([[0.0], np.cumsum(seg)])

    # ------------------------------------------------------------------ queries
    def closest_waypoint_index(self, x: float, y: float) -> int:
        d = np.hypot(self.waypoints[:, 0] - x, self.waypoints[:, 1] - y)
        return int(np.argmin(d))

    def progress(self, x: float, y: float) -> float:
        """Arc-length progress (in meters) along the centerline at the closest point."""
        idx = self.closest_waypoint_index(x, y)
        return float(self._cum_lengths[idx])

    def progress_normalized(self, x: float, y: float) -> float:
        return self.progress(x, y) / self.total_length

    def signed_lateral_offset(self, x: float, y: float) -> float:
        """Signed perpendicular distance from centerline (positive = left of direction of travel)."""
        idx = self.closest_waypoint_index(x, y)
        nxt = (idx + 1) % len(self.waypoints)
        p = self.waypoints[idx]
        q = self.waypoints[nxt]
        tangent = q - p
        tangent /= (np.linalg.norm(tangent) + 1e-9)
        normal = np.array([-tangent[1], tangent[0]])  # left-hand perpendicular
        return float(np.dot(np.array([x, y]) - p, normal))

    def is_on_track(self, x: float, y: float) -> bool:
        return abs(self.signed_lateral_offset(x, y)) <= self.track_width / 2.0

    def start_pose(self, lane_offset: float = 0.0, slot: int = 0) -> Tuple[float, float, float]:
        """Pose at the start/finish line. `slot` separates two cars longitudinally."""
        L = self.straight_length
        # start/finish is at the middle of the bottom straight, heading +x
        x = -slot * 0.6  # car length spacing; slot 0 is leader, slot 1 is behind
        y = -self.centerline_radius + lane_offset
        theta = 0.0
        # clamp to bottom straight
        x = max(-L / 2 + 0.2, min(L / 2 - 0.2, x))
        return x, y, theta

    def finish_line_crossed(
        self, prev_xy: Tuple[float, float], xy: Tuple[float, float]
    ) -> bool:
        """Detect crossing the line x=0 going from -x to +x while on bottom straight."""
        px, py = prev_xy
        x, y = xy
        on_bottom = (py < -self.centerline_radius * 0.5) and (y < -self.centerline_radius * 0.5)
        return on_bottom and (px < 0.0 <= x)
