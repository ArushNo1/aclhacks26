"""Overhead camera bridge.

Pulls the raw H.264 stream from the AWS DeepLens overhead camera over SSH
and decodes it into JPEGs via ffmpeg. A single shared producer task runs
for the lifetime of the app; HTTP viewers subscribe to the latest frame
so multiple dashboard tabs do not each spawn ssh+ffmpeg.

Configuration via env vars:
    OVERHEAD_SSH_HOST   default aws_cam@10.11.0.151
    OVERHEAD_SSH_PASS   default arushno1   (move to a key for anything but the LAN demo)
    OVERHEAD_SRC_PATH   default /opt/awscam/out/ch1_out.h264
    OVERHEAD_FPS        default 15
    OVERHEAD_JPEG_Q     default 6   (ffmpeg -q:v scale, lower = better)
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Optional


SSH_HOST = os.environ.get("OVERHEAD_SSH_HOST", "aws_cam@10.11.0.151")
SSH_PASS = os.environ.get("OVERHEAD_SSH_PASS", "arushno1")
SRC_PATH = os.environ.get("OVERHEAD_SRC_PATH", "/opt/awscam/out/ch1_out.h264")
FPS = float(os.environ.get("OVERHEAD_FPS", "15"))
JPEG_Q = int(os.environ.get("OVERHEAD_JPEG_Q", "6"))

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"


class OverheadBridge:
    """Single-producer, many-consumer JPEG fanout from the overhead camera."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._last_jpeg: Optional[bytes] = None
        self._version: int = 0
        self._last_frame_ts: float = 0.0
        self._stopping = False

    # ------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="overhead-bridge")

    async def stop(self) -> None:
        self._stopping = True
        if self._proc is not None and self._proc.returncode is None:
            try:
                self._proc.kill()
            except ProcessLookupError:
                pass
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        self._task = None
        self._proc = None

    # ------------------------------------------------------------- accessors
    def last_jpeg(self) -> Optional[bytes]:
        return self._last_jpeg

    def version(self) -> int:
        return self._version

    def online(self) -> bool:
        return (time.time() - self._last_frame_ts) < 5.0 if self._last_frame_ts else False

    # ------------------------------------------------------------- internals
    def _build_cmd(self) -> list[str]:
        # bash -c so the pipe is interpreted by a shell; sshpass keeps the
        # password out of argv inspection by ssh itself.
        ssh = (
            f"sshpass -p {SSH_PASS} ssh "
            f"-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"-o ServerAliveInterval=5 -o ConnectTimeout=5 "
            f"-T {SSH_HOST} 'cat {SRC_PATH}'"
        )
        ff = (
            "ffmpeg -hide_banner -loglevel error -fflags nobuffer -flags low_delay "
            f"-i - -an -f image2pipe -vcodec mjpeg -q:v {JPEG_Q} -r {FPS} -"
        )
        return ["bash", "-c", f"{ssh} | {ff}"]

    async def _run(self) -> None:
        backoff = 1.0
        while not self._stopping:
            try:
                await self._spawn_and_read()
                backoff = 1.0
            except Exception as e:
                print(f"[overhead] producer error: {e}")
            if self._stopping:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 10.0)

    async def _spawn_and_read(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            *self._build_cmd(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        assert self._proc.stdout is not None
        buf = bytearray()
        try:
            while not self._stopping:
                chunk = await self._proc.stdout.read(65536)
                if not chunk:
                    break
                buf.extend(chunk)
                # Drain every complete JPEG in the buffer; keep only the trailing partial.
                while True:
                    s = buf.find(SOI)
                    if s == -1:
                        buf.clear()
                        break
                    e = buf.find(EOI, s + 2)
                    if e == -1:
                        if s > 0:
                            del buf[:s]
                        break
                    jpg = bytes(buf[s : e + 2])
                    del buf[: e + 2]
                    self._last_jpeg = jpg
                    self._version += 1
                    self._last_frame_ts = time.time()
        finally:
            if self._proc.returncode is None:
                try:
                    self._proc.kill()
                except ProcessLookupError:
                    pass
            await self._proc.wait()
