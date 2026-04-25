#!/usr/bin/env python3
"""Grab frames from /dev/videoN and publish JPEGs to MQTT topic car/{CAR_ID}/frame."""
import os
import time
import cv2
import paho.mqtt.client as mqtt

CAR_ID = os.environ.get("CAR_ID", "1")
CAM_DEV = int(os.environ.get("CAM_DEV", "0"))
WIDTH = int(os.environ.get("WIDTH", "320"))
HEIGHT = int(os.environ.get("HEIGHT", "240"))
FPS = int(os.environ.get("FPS", "15"))
JPEG_Q = int(os.environ.get("JPEG_Q", "75"))
BROKER = os.environ.get("MQTT_BROKER", "10.11.0.203")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = f"car/{CAR_ID}/frame"


def main() -> None:
    cap = cv2.VideoCapture(CAM_DEV, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)
    if not cap.isOpened():
        raise RuntimeError(f"failed to open /dev/video{CAM_DEV}")

    client = mqtt.Client(client_id=f"car-{CAR_ID}-cam")
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()
    print(f"[cam] /dev/video{CAM_DEV} -> mqtt://{BROKER}:{PORT}/{TOPIC} @ {FPS}fps")

    period = 1.0 / FPS
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_Q]
    n = 0
    t_log = time.time()
    while True:
        t0 = time.time()
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue
        ok, jpg = cv2.imencode(".jpg", frame, encode_params)
        if not ok:
            continue
        client.publish(TOPIC, jpg.tobytes(), qos=0, retain=False)
        n += 1
        if time.time() - t_log > 5.0:
            print(f"[cam] {n / (time.time() - t_log):.1f} fps")
            n, t_log = 0, time.time()
        dt = time.time() - t0
        if dt < period:
            time.sleep(period - dt)


if __name__ == "__main__":
    main()
