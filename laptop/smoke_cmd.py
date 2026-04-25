#!/usr/bin/env python3
"""Smoke test the command path: pulse forward, stop, pulse left, stop.
Lift the car off the ground first — wheels will spin.
"""
import json
import os
import time

import paho.mqtt.client as mqtt

CAR_ID = os.environ.get("CAR_ID", "1")
BROKER = os.environ.get("MQTT_BROKER", "localhost")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = f"car/{CAR_ID}/cmd"


def send(client: mqtt.Client, steer: float, throttle: float) -> None:
    payload = json.dumps({"steer": steer, "throttle": throttle})
    client.publish(TOPIC, payload, qos=0)
    print(f"-> {payload}")


def main() -> None:
    client = mqtt.Client(client_id=f"smoke-{CAR_ID}")
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()
    try:
        send(client, 0.0, 0.3); time.sleep(1.0)
        send(client, 0.0, 0.0); time.sleep(0.5)
        send(client, -0.6, 0.2); time.sleep(1.0)
        send(client, 0.6, 0.2); time.sleep(1.0)
        send(client, 0.0, 0.0); time.sleep(0.2)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
