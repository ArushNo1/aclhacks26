"""
Two render paths:

1. Top-down spectator view (pygame Surface). Used for the human window.
2. Per-car first-person RGB image (np.uint8 HxWx3). Used as the policy observation.

The first-person view is a forward bird's-eye crop with a simple perspective
warp — close-to-the-camera regions appear wider than far ones — so the CNN
sees a convergence-of-track-edges cue similar to the DeepRacer's onboard camera.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np

from .car import CAR_LENGTH_M, CAR_WIDTH_M, Car
from .domain_rand import DomainRand
from .track import Track


# First-person camera footprint on the ground (car frame, forward = +x_car):
FP_FORWARD_NEAR_M = 0.10
FP_FORWARD_FAR_M = 3.5
FP_LATERAL_NEAR_M = 0.30   # half-width of the trapezoid at near edge
FP_LATERAL_FAR_M = 2.5     # half-width at far edge (wider = more horizon)

# spectator window settings
PIXELS_PER_METER = 50


def render_first_person(
    track: Track,
    car: Car,
    opponent: Optional[Car],
    dr: DomainRand,
    H: int = 120,
    W: int = 160,
) -> np.ndarray:
    """Returns an HxWx3 uint8 image as the policy's observation."""
    # For each output pixel, pick a ground point in the car's frame, then rotate
    # into world frame and classify.
    #
    # u in [0, W) -> lateral; v in [0, H) -> forward. v=H-1 is "near", v=0 is "far".
    v = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]   # 0=far, 1=near
    u = np.linspace(-1.0, 1.0, W, dtype=np.float32)[None, :]  # -1=left, +1=right

    # forward distance in car frame (linear from far to near as v grows)
    forward = FP_FORWARD_FAR_M + (FP_FORWARD_NEAR_M - FP_FORWARD_FAR_M) * v
    # lateral half-width depends on v (perspective trapezoid)
    half_w = FP_LATERAL_FAR_M + (FP_LATERAL_NEAR_M - FP_LATERAL_FAR_M) * v
    # u=+1 (right of image) -> lateral<0 (right of car, since +y is left of car)
    lateral = -u * half_w

    # apply optional camera pitch jitter (rotates the forward axis around lateral axis)
    pitch = math.radians(dr.camera_pitch_deg)
    forward = forward * math.cos(pitch)  # negligible at small angles, kept for completeness

    # broadcast to HxW grids of (xc, yc) in car frame
    xc = np.broadcast_to(forward, (H, W))
    yc = np.broadcast_to(lateral, (H, W))

    # rotate into world frame
    cos_t = math.cos(car.heading)
    sin_t = math.sin(car.heading)
    xw = car.state.x + xc * cos_t - yc * sin_t
    yw = car.state.y + xc * sin_t + yc * cos_t

    img = _classify_ground(track, xw, yw, dr)

    # paint opponent if visible
    if opponent is not None:
        _paint_opponent(img, car, opponent, H, W)

    # brightness
    img = np.clip(img.astype(np.float32) * dr.brightness, 0, 255).astype(np.uint8)
    return img


def _classify_ground(track: Track, xw: np.ndarray, yw: np.ndarray, dr: DomainRand) -> np.ndarray:
    """O(1)-per-pixel oval classifier. Each pixel is in one of 4 segments
    (bottom straight, top straight, right arc, left arc); the segment is
    selected by sign and range of (x, y) and the lateral distance to the
    centerline is computed analytically.
    """
    L = track.straight_length
    R = track.centerline_radius
    W_half = track.track_width / 2.0
    line_thickness = 0.04

    in_straight_x = (xw >= -L / 2.0) & (xw <= L / 2.0)

    # straight regions: distance to nearest centerline (y = ±R)
    d_straight = np.minimum(np.abs(yw - R), np.abs(yw + R))

    # arc regions: distance to nearest arc centerline (radius R around (±L/2, 0))
    use_right_arc = xw > 0
    cx = np.where(use_right_arc, L / 2.0, -L / 2.0)
    dist_to_center = np.sqrt((xw - cx) ** 2 + yw ** 2)
    d_arc = np.abs(dist_to_center - R)

    d = np.where(in_straight_x, d_straight, d_arc)

    on_track = d <= W_half
    on_edge = np.abs(d - W_half) < line_thickness
    on_centerline = d < line_thickness

    img = np.empty(xw.shape + (3,), dtype=np.uint8)
    img[:] = dr.grass_color
    img[on_track] = dr.track_color
    img[on_edge] = dr.line_color
    img[on_centerline] = dr.line_color
    return img


def _paint_opponent(img: np.ndarray, ego: Car, opp: Car, H: int, W: int) -> None:
    """Paint a colored rectangle for the opponent if it falls inside our FP view."""
    dx = opp.state.x - ego.state.x
    dy = opp.state.y - ego.state.y
    cos_t = math.cos(-ego.heading)
    sin_t = math.sin(-ego.heading)
    xc = dx * cos_t - dy * sin_t  # forward in ego frame
    yc = dx * sin_t + dy * cos_t  # lateral

    if not (FP_FORWARD_NEAR_M <= xc <= FP_FORWARD_FAR_M):
        return

    # invert the (forward, lateral) -> (u, v) mapping used in render_first_person
    v_norm = (xc - FP_FORWARD_FAR_M) / (FP_FORWARD_NEAR_M - FP_FORWARD_FAR_M)
    half_w = FP_LATERAL_FAR_M + (FP_LATERAL_NEAR_M - FP_LATERAL_FAR_M) * v_norm
    if half_w <= 0:
        return
    u_norm = -yc / half_w  # match the lateral flip in render_first_person
    if abs(u_norm) > 1.0:
        return

    cu = int((u_norm + 1) * 0.5 * (W - 1))
    cv = int(v_norm * (H - 1))
    # apparent size shrinks with distance
    size = max(2, int(28 * (1.0 - v_norm) + 12 * v_norm))  # roughly: bigger when near
    half = size // 2
    u0, u1 = max(0, cu - half), min(W, cu + half)
    v0, v1 = max(0, cv - half), min(H, cv + size)  # opponent extends "down" toward camera
    img[v0:v1, u0:u1] = (220, 60, 60)  # red rectangle


# ------------------------------------------------------------------ spectator
def render_spectator(track: Track, cars, dr: DomainRand, size_px: int = 600) -> np.ndarray:
    """Top-down RGB image of the whole track and both cars. Returned as HxWx3 uint8."""
    img = np.full((size_px, size_px, 3), dr.grass_color, dtype=np.uint8)
    cx, cy = size_px // 2, size_px // 2

    def w2p(xw, yw):
        return int(cx + xw * PIXELS_PER_METER), int(cy - yw * PIXELS_PER_METER)

    # draw track band
    wp = track.waypoints
    pts = np.array([w2p(p[0], p[1]) for p in wp], dtype=np.int32)
    # widened polyline -> approximate with thick line via pygame? we use cv2 here.
    import cv2
    cv2.polylines(img, [pts], isClosed=True, color=dr.track_color,
                  thickness=int(track.track_width * PIXELS_PER_METER))
    cv2.polylines(img, [pts], isClosed=True, color=dr.line_color, thickness=2)

    # finish line marker
    fx0, fy0 = w2p(0.0, -track.centerline_radius - track.track_width / 2)
    fx1, fy1 = w2p(0.0, -track.centerline_radius + track.track_width / 2)
    cv2.line(img, (fx0, fy0), (fx1, fy1), (255, 255, 255), 3)

    # draw each car as an oriented rectangle
    colors = [(60, 200, 255), (220, 80, 80)]
    for car, color in zip(cars, colors):
        _draw_car(img, car, color, w2p)

    return img


def _draw_car(img: np.ndarray, car: Car, color, w2p) -> None:
    import cv2
    L = CAR_LENGTH_M / 2
    Wd = CAR_WIDTH_M / 2
    corners_local = np.array([[ L,  Wd], [ L, -Wd], [-L, -Wd], [-L,  Wd]], dtype=np.float32)
    cos_t = math.cos(car.heading)
    sin_t = math.sin(car.heading)
    R = np.array([[cos_t, -sin_t], [sin_t, cos_t]], dtype=np.float32)
    corners_world = (corners_local @ R.T) + np.array([car.state.x, car.state.y], dtype=np.float32)
    pts = np.array([w2p(p[0], p[1]) for p in corners_world], dtype=np.int32)
    cv2.fillPoly(img, [pts], color)
    # heading indicator
    front = (car.state.x + math.cos(car.heading) * L * 1.4,
             car.state.y + math.sin(car.heading) * L * 1.4)
    cv2.circle(img, w2p(*front), 3, (255, 255, 255), -1)
