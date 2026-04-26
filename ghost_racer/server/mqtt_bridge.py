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
import os
import time
from typing import Any, Dict, Optional, Set

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
        is_binary = topic.endswith("/frame") or len(payload) > MAX_PAYLOAD_PREVIEW
        if is_binary:
            preview = f"{len(payload) / 1024.0:.1f} kB · binary"
        else:
            try:
                preview = payload.decode("utf-8", errors="replace")
            except Exception:
                preview = repr(payload)[:MAX_PAYLOAD_PREVIEW]
        record = {
            "ts": time.time(),
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
