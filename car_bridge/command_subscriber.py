#!/usr/bin/env python3
"""Subscribe to MQTT car/{CAR_ID}/cmd and republish to ROS 2 /ctrl_pkg/servo_msg.

Payload format on MQTT (JSON):
    {"steer": -1.0..1.0, "throttle": -1.0..1.0}
"""
import json
import os

import paho.mqtt.client as mqtt
import rclpy
from deepracer_interfaces_pkg.msg import ServoCtrlMsg
from deepracer_interfaces_pkg.srv import ActiveStateSrv
from rclpy.node import Node

CAR_ID = os.environ.get("CAR_ID", "1")
BROKER = os.environ.get("MQTT_BROKER", "10.11.0.203")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = f"car/{CAR_ID}/cmd"
MANUAL_MODE = 1  # ctrl_pkg vehicle_state: 0=stopped, 1=manual, 2=autonomous, 3=calibration


class Bridge(Node):
    def __init__(self) -> None:
        super().__init__(f"car_{CAR_ID}_cmd_bridge")
        self.pub = self.create_publisher(ServoCtrlMsg, "/ctrl_pkg/servo_msg", 10)
        self._set_manual_mode()

    def _set_manual_mode(self) -> None:
        cli = self.create_client(ActiveStateSrv, "/ctrl_pkg/vehicle_state")
        if not cli.wait_for_service(timeout_sec=3.0):
            self.get_logger().warn("vehicle_state service unavailable; skipping mode set")
            return
        req = ActiveStateSrv.Request()
        req.state = MANUAL_MODE
        fut = cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=3.0)
        self.get_logger().info(f"vehicle_state -> manual ({MANUAL_MODE})")

    def on_cmd(self, payload: bytes) -> None:
        try:
            d = json.loads(payload.decode("utf-8"))
        except Exception as e:
            self.get_logger().warn(f"bad payload: {e}")
            return
        msg = ServoCtrlMsg()
        msg.angle = float(d.get("steer", 0.0))
        msg.throttle = float(d.get("throttle", 0.0))
        self.pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = Bridge()
    client = mqtt.Client(client_id=f"car-{CAR_ID}-cmd")
    client.on_message = lambda c, u, m: node.on_cmd(m.payload)
    client.connect(BROKER, PORT, keepalive=60)
    client.subscribe(TOPIC, qos=0)
    client.loop_start()
    print(f"[cmd] mqtt://{BROKER}:{PORT}/{TOPIC} -> /ctrl_pkg/servo_msg")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
