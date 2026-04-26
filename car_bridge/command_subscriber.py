#!/usr/bin/env python3
"""Subscribe to MQTT car/{CAR_ID}/cmd and POST to the DeepRacer device HTTP API.

Bypasses ROS to avoid the broken DDS discovery on this firmware. The web UI
proves the HTTP path works end-to-end through the same ctrl_node.

Payload format on MQTT (JSON):
    {"steer": -1.0..1.0, "throttle": -1.0..1.0}
"""
import json
import os
import re
import time
import urllib3

import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CAR_ID = os.environ.get("CAR_ID", "1")
BROKER = os.environ.get("MQTT_BROKER", "10.11.0.203")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = f"car/{CAR_ID}/cmd"

DEVICE_HOST = os.environ.get("DEVICE_HOST", "https://localhost")
DEVICE_PASSWORD = os.environ.get("DEVICE_PASSWORD")  # sticker password
MAX_SPEED = float(os.environ.get("MAX_SPEED", "1.0"))


class DeviceClient:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.verify = False
        self.csrf = None
        self._login()
        # Refresh CSRF after login from the home page (token rotates on auth).
        try:
            r = self.s.get(f"{DEVICE_HOST}/", timeout=5)
            m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text) \
                or re.search(r'name="csrf-token"[^>]*content="([^"]+)"', r.text)
            self.csrf = m.group(1) if m else None
            if self.csrf:
                self.s.headers["X-CSRFToken"] = self.csrf
                print("[cmd] CSRF token loaded for subsequent requests")
        except Exception as e:
            print(f"[cmd] post-login CSRF fetch failed: {e}")

    def _login(self) -> None:
        if not DEVICE_PASSWORD:
            print("[cmd] DEVICE_PASSWORD not set; assuming session not required")
            return
        # Step 1: GET /login to get CSRF token + session cookie.
        try:
            r = self.s.get(f"{DEVICE_HOST}/login", timeout=5)
        except Exception as e:
            print(f"[cmd] GET /login failed: {e}")
            return
        m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
        token = m.group(1) if m else None
        if not token:
            # Some firmwares put it in a meta tag.
            m = re.search(r'name="csrf-token"[^>]*content="([^"]+)"', r.text)
            token = m.group(1) if m else None
        if not token:
            print("[cmd] WARNING: no CSRF token found on /login; trying without")
        # Step 2: POST credentials.
        data = {"password": DEVICE_PASSWORD}
        if token:
            data["csrf_token"] = token
        try:
            r = self.s.post(
                f"{DEVICE_HOST}/login",
                data=data,
                headers={"X-CSRFToken": token} if token else {},
                timeout=5,
                allow_redirects=True,
            )
            if r.status_code in (200, 204, 302):
                print(f"[cmd] login ok ({r.status_code})")
            else:
                print(f"[cmd] login returned {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[cmd] POST /login failed: {e}")

    def set_manual_mode(self) -> None:
        for path, payload in (
            ("/api/vehicle_control", {"drive_mode": "manual"}),
            ("/api/start_stop", {"start_stop": "start"}),
        ):
            try:
                r = self.s.put(f"{DEVICE_HOST}{path}", json=payload, timeout=3)
                print(f"[cmd] {path} -> {r.status_code}")
            except Exception as e:
                print(f"[cmd] {path} error: {e}")

    def drive(self, angle: float, throttle: float) -> None:
        body = {
            "angle": max(-1.0, min(1.0, angle)),
            "throttle": max(-1.0, min(1.0, throttle)),
            "max_speed": MAX_SPEED,
        }
        try:
            self.s.put(f"{DEVICE_HOST}/api/manual_drive", json=body, timeout=1)
        except Exception as e:
            print(f"[cmd] drive error: {e}")


def main() -> None:
    dev = DeviceClient()
    dev.set_manual_mode()

    client = mqtt.Client(client_id=f"car-{CAR_ID}-cmd")

    def on_msg(_c, _u, m):
        try:
            d = json.loads(m.payload.decode("utf-8"))
        except Exception as e:
            print(f"[cmd] bad payload: {e}")
            return
        dev.drive(float(d.get("steer", 0.0)), float(d.get("throttle", 0.0)))

    client.on_message = on_msg
    client.connect(BROKER, PORT, keepalive=60)
    client.subscribe(TOPIC, qos=0)
    client.loop_start()
    print(f"[cmd] mqtt://{BROKER}:{PORT}/{TOPIC} -> {DEVICE_HOST}/api/manual_drive")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
