# car_bridge

Runs on the DeepRacer. Bridges MQTT ↔ ROS 2 so the laptop can drive the car
and receive its camera feed without going through AWS's broken `camera_node`.

## One-time install on the car

```
ssh deepracer@<car-ip>
sudo apt update && sudo apt install -y python3-pip mosquitto-clients
pip3 install --user opencv-python paho-mqtt
sudo usermod -aG video deepracer  # then log out / back in
```

## Laptop setup (Mosquitto broker)

```
sudo dnf install -y mosquitto                       # Fedora
sudo systemctl enable --now mosquitto

# allow LAN clients (default is loopback only on some distros)
echo -e "listener 1883 0.0.0.0\nallow_anonymous true" | \
  sudo tee /etc/mosquitto/conf.d/lan.conf
sudo systemctl restart mosquitto

# poke a hole if firewalld is up
sudo firewall-cmd --add-port=1883/tcp --permanent
sudo firewall-cmd --reload
```

Confirm broker reachability from the car:

```
mosquitto_pub -h <laptop-ip> -t test -m hi
```

## Run the bridge

On the car:

```
cd ~/aclhacks26/car_bridge          # wherever you cloned/scp'd the repo
CAR_ID=1 MQTT_BROKER=<laptop-ip> ./start_bridge.sh
```

That kills the wedged AWS `camera_node`, then starts:
- `camera_publisher.py` → reads `/dev/video0`, publishes JPEGs to `car/1/frame`
- `command_subscriber.py` → reads JSON from `car/1/cmd`, publishes to ROS 2 `/ctrl_pkg/servo_msg`

## Verify from the laptop

```
# camera feed
python3 laptop/view_frames.py

# motor smoke test (LIFT THE CAR OFF THE GROUND)
python3 laptop/smoke_cmd.py
```

## MQTT topics

| Topic | Direction | Payload |
|---|---|---|
| `car/{id}/frame` | car → laptop | raw JPEG bytes |
| `car/{id}/cmd`   | laptop → car | JSON `{"steer": -1..1, "throttle": -1..1}` |
| `race/{event}`   | many → many  | TBD (M5: race tower) |

## Notes

- We deliberately keep `deepracer-core` running for `ctrl_pkg` and `servo_pkg`.
  Only `camera_node` is killed (it grabs `/dev/video0` but never publishes).
- If `camera_node` respawns under you, the launch file needs patching — but
  on current firmware it stays dead after `pkill`.
- `ServoCtrlMsg.angle` and `.throttle` are clamped to [-1.0, 1.0] inside
  the AWS ctrl_node before being mapped to PWM via the saved calibration.
