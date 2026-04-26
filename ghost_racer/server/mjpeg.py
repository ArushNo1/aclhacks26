"""multipart/x-mixed-replace MJPEG streaming.

Wraps a frame-source callable (returns RGB or BGR HxWx3 uint8) into an
async generator that yields JPEG-encoded multipart parts. Use as the body
of a StreamingResponse with media_type='multipart/x-mixed-replace; boundary=...'.

Browsers natively render MJPEG streams in <img> tags, so the dashboard
can drop these endpoints in as <img src="/stream/spectator.mjpg"> without
any JS.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Callable, Optional

import cv2
import numpy as np


BOUNDARY = "ghostracerframe"
JPEG_Q = 70  # quality 0-100; 70 is a good speed/size tradeoff for ~600x600


async def mjpeg_stream(
    frame_src: Callable[[], Optional[np.ndarray]],
    fps: float = 20.0,
    swap_rgb_to_bgr: bool = True,
) -> AsyncIterator[bytes]:
    """Yield multipart JPEG frames at up to `fps`.

    `frame_src` is a callable returning the current frame (HxWx3 uint8,
    in RGB if swap_rgb_to_bgr=True since cv2 wants BGR for JPEG encoding).
    Returning None or an array-of-zeros means "no new frame yet" — we
    still emit a small placeholder so the connection stays alive.
    """
    period = 1.0 / max(fps, 1.0)
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_Q]
    while True:
        frame = frame_src()
        if frame is None:
            await asyncio.sleep(period)
            continue
        if swap_rgb_to_bgr:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        ok, jpg = cv2.imencode(".jpg", frame, encode_params)
        if not ok:
            await asyncio.sleep(period)
            continue
        chunk = (
            f"--{BOUNDARY}\r\n"
            f"Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(jpg)}\r\n\r\n"
        ).encode("ascii") + jpg.tobytes() + b"\r\n"
        yield chunk
        await asyncio.sleep(period)
