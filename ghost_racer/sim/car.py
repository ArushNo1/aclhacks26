"""
Kinematic bicycle model. Tuned to roughly match a 1/18-scale AWS DeepRacer
so policies trained here transfer with action-scale info preserved.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# --- physical constants (DeepRacer-ish) ---
WHEELBASE_M = 0.165       # ~16.5 cm
MAX_STEER_RAD = 0.52      # ~30 deg, mech limit
MAX_SPEED_MPS = 2.0       # cap; DeepRacer race-mode tops out ~2 m/s
ACCEL_MPS2 = 3.0          # full-throttle accel before drag
DRAG_COEFF = 0.6          # 1/s, linear drag => v_terminal ~ a/k
REVERSE_FACTOR = 0.4      # reverse is slower than forward
CAR_LENGTH_M = 0.30
CAR_WIDTH_M = 0.18


@dataclass
class CarState:
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0  # heading, radians, +x direction at theta=0
    v: float = 0.0      # signed forward speed, m/s


class Car:
    """One car. Action space matches what the DeepRacer's controller accepts."""

    def __init__(self, x: float = 0.0, y: float = 0.0, theta: float = 0.0):
        self.state = CarState(x=x, y=y, theta=theta, v=0.0)

    def reset(self, x: float, y: float, theta: float) -> None:
        self.state = CarState(x=x, y=y, theta=theta, v=0.0)

    def step(self, steer: float, throttle: float, dt: float) -> None:
        """
        steer    in [-1, 1] -> physical steering angle ±MAX_STEER_RAD
        throttle in [-1, 1] -> +1 full forward, -1 full reverse, 0 coast
        """
        steer = max(-1.0, min(1.0, float(steer)))
        throttle = max(-1.0, min(1.0, float(throttle)))

        s = self.state
        accel = throttle * ACCEL_MPS2
        if throttle < 0:
            accel *= REVERSE_FACTOR

        # integrate speed with linear drag
        s.v += accel * dt - DRAG_COEFF * s.v * dt

        # cap speed
        v_cap = MAX_SPEED_MPS if s.v >= 0 else MAX_SPEED_MPS * REVERSE_FACTOR
        s.v = max(-v_cap, min(v_cap, s.v))

        # bicycle update
        delta = steer * MAX_STEER_RAD
        if abs(delta) < 1e-4:
            s.x += s.v * math.cos(s.theta) * dt
            s.y += s.v * math.sin(s.theta) * dt
        else:
            yaw_rate = s.v * math.tan(delta) / WHEELBASE_M
            s.theta += yaw_rate * dt
            s.x += s.v * math.cos(s.theta) * dt
            s.y += s.v * math.sin(s.theta) * dt

        # wrap heading
        s.theta = math.atan2(math.sin(s.theta), math.cos(s.theta))

    @property
    def position(self):
        return (self.state.x, self.state.y)

    @property
    def heading(self) -> float:
        return self.state.theta

    @property
    def speed(self) -> float:
        return self.state.v


def cars_collide(a: Car, b: Car) -> bool:
    dx = a.state.x - b.state.x
    dy = a.state.y - b.state.y
    # circle approximation around each car
    radius = 0.5 * math.hypot(CAR_LENGTH_M, CAR_WIDTH_M)
    return math.hypot(dx, dy) < 2 * radius
