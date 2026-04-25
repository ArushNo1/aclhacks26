#!/usr/bin/env python3
"""Subscribe to car/{CAR_ID}/frame and display the live MJPEG over MQTT."""
import os
import sys

import cv2
import numpy as np
import paho.mqtt.client as mqtt

CAR_ID = os.environ.get("CAR_ID", "1")
BROKER = os.environ.get("MQTT_BROKER", "localhost")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = f"car/{CAR_ID}/frame"


def on_msg(_client, _userdata, msg) -> None:
    arr = np.frombuffer(msg.payload, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return
    cv2.imshow(TOPIC, img)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        sys.exit(0)


def main() -> None:
    client = mqtt.Client(client_id=f"viewer-{CAR_ID}")
    client.on_message = on_msg
    client.connect(BROKER, PORT, keepalive=60)
    client.subscribe(TOPIC, qos=0)
    print(f"[view] mqtt://{BROKER}:{PORT}/{TOPIC} (q to quit)")
    client.loop_forever()


if __name__ == "__main__":
    main()
