"""Optional MQTT pass-through for Act 4 DEBUG.

Subscribes once to `car/+/+` (and any other topics you publish to) and
fans messages out to a set of asyncio Queues so /ws/mqtt clients get a
live tail of the broker activity. Frame topics (binary JPEG payloads)
are summarized rather than forwarded raw.

If no broker is running, MqttBridge.start() raises and the app gracefully
disables Act 4's MQTT log.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

try:
    import paho.mqtt.client as mqtt
    HAVE_PAHO = True
except Exception:
    HAVE_PAHO = False


CAR_ID = os.environ.get("CAR_ID", "1")
BROKER = os.environ.get("MQTT_BROKER", "localhost")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
SUBSCRIBE_TOPICS = ["car/+/+", "race/+", "device/+/+", "leap/+", "trainer/+"]
MAX_PAYLOAD_PREVIEW = 160  # chars; binary topics are summarized to size

CAR_TOPIC_RE = re.compile(r"^car/([^/]+)/(frame|cmd)$")
FRAME_WINDOW_S = 5.0       # rolling window for FPS / cmd-rate
ONLINE_THRESHOLD_S = 2.0   # last frame age above this → OFFLINE


class MqttBridge:
    def __init__(self) -> None:
        if not HAVE_PAHO:
            raise RuntimeError("paho-mqtt not installed")
        self._client = mqtt.Client(client_id=f"ghostracer-server-{int(time.time())}")
        self._client.on_message = self._on_message
        self._client.on_connect = self._on_connect
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._subs: Set[asyncio.Queue[Dict[str, Any]]] = set()
        self._connected = False
        self._msg_count = 0
        self._msg_window_start = time.time()
        # Per-car telemetry: keyed by car id (string).
        # Each entry: {frame_ts, cmd_ts, frame_bytes, frame_times: deque, cmd_times: deque, last_jpeg: bytes}
        self._cars: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        # paho's `connect` is blocking; do it on a thread.
        await asyncio.to_thread(self._client.connect, BROKER, PORT, 60)
        self._client.loop_start()

    async def stop(self) -> None:
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass

    # ------------------------------------------------------- subscriptions
    def subscribe(self) -> "asyncio.Queue[Dict[str, Any]]":
        q: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=200)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: "asyncio.Queue[Dict[str, Any]]") -> None:
        self._subs.discard(q)

    # ----------------------------------------------------------- monitoring
    def status(self) -> str:
        return "ON" if self._connected else "CONNECTING"

    def msg_rate(self) -> float:
        dt = time.time() - self._msg_window_start
        if dt < 1e-3:
            return 0.0
        return self._msg_count / dt

    def client_count(self) -> int:
        return len(self._subs)

    def broker_url(self) -> str:
        return f"{BROKER}:{PORT}"

    def publish_cmd(self, car_id: str, steer: float, throttle: float) -> None:
        """Publish a tank-drive command to car/{id}/cmd as JSON."""
        if not self._connected:
            return
        topic = f"car/{car_id}/cmd"
        payload = json.dumps({
            "steer": float(steer),
            "throttle": float(throttle),
        })
        try:
            self._client.publish(topic, payload, qos=0, retain=False)
        except Exception:
            pass

    def last_jpeg(self, car_id: str) -> Optional[bytes]:
        """Latest JPEG payload received on car/{id}/frame, or None."""
        car = self._cars.get(car_id)
        if car is None:
            return None
        jpg = car.get("last_jpeg")
        return jpg if jpg else None

    def cars(self) -> List[Dict[str, Any]]:
        """Snapshot of per-car connection state, sorted by id."""
        now = time.time()
        out: List[Dict[str, Any]] = []
        for cid in sorted(self._cars.keys()):
            c = self._cars[cid]
            frame_ts: float = c["frame_ts"]
            cmd_ts: float = c["cmd_ts"]
            frame_times: Deque[float] = c["frame_times"]
            cmd_times: Deque[float] = c["cmd_times"]
            # Trim windows
            cutoff = now - FRAME_WINDOW_S
            while frame_times and frame_times[0] < cutoff:
                frame_times.popleft()
            while cmd_times and cmd_times[0] < cutoff:
                cmd_times.popleft()
            frame_age = (now - frame_ts) if frame_ts > 0 else float("inf")
            online = frame_age < ONLINE_THRESHOLD_S
            out.append({
                "id": cid,
                "online": online,
                "frame_age_s": frame_age if frame_ts > 0 else None,
                "cmd_age_s": (now - cmd_ts) if cmd_ts > 0 else None,
                "fps": len(frame_times) / FRAME_WINDOW_S,
                "cmd_rate": len(cmd_times) / FRAME_WINDOW_S,
                "last_frame_kb": c["frame_bytes"] / 1024.0,
            })
        return out

    # ----------------------------------------------------------- internals
    def _on_connect(self, client, userdata, flags, rc, *args, **kwargs) -> None:
        if rc == 0:
            self._connected = True
            for topic in SUBSCRIBE_TOPICS:
                client.subscribe(topic, qos=0)

    def _on_message(self, client, userdata, msg) -> None:
        # Summarize binary / large payloads
        topic = msg.topic
        payload = msg.payload
        now = time.time()
        # Track per-car activity for /api/health
        m = CAR_TOPIC_RE.match(topic)
        if m:
            cid, kind = m.group(1), m.group(2)
            car = self._cars.setdefault(cid, {
                "frame_ts": 0.0,
                "cmd_ts": 0.0,
                "frame_bytes": 0,
                "frame_times": deque(),
                "cmd_times": deque(),
                "last_jpeg": b"",
            })
            if kind == "frame":
                car["frame_ts"] = now
                car["frame_bytes"] = len(payload)
                car["frame_times"].append(now)
                car["last_jpeg"] = bytes(payload)
            elif kind == "cmd":
                car["cmd_ts"] = now
                car["cmd_times"].append(now)
        is_binary = topic.endswith("/frame") or len(payload) > MAX_PAYLOAD_PREVIEW
        if is_binary:
            preview = f"{len(payload) / 1024.0:.1f} kB · binary"
        else:
            try:
                preview = payload.decode("utf-8", errors="replace")
            except Exception:
                preview = repr(payload)[:MAX_PAYLOAD_PREVIEW]
        record = {
            "ts": now,
            "topic": topic,
            "payload": preview,
            "size": len(payload),
        }
        self._msg_count += 1
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._fanout, record)

    def _fanout(self, record: Dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(record)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                except Exception:
                    pass
                try:
                    q.put_nowait(record)
                except Exception:
                    pass
