#!/usr/bin/env bash
# Run on the DeepRacer. Releases /dev/video0 from the broken AWS camera_node,
# then starts our camera publisher and command subscriber.
set -eo pipefail

# ROS setup scripts reference unbound vars; suppress nounset while sourcing.
source /opt/ros/foxy/setup.bash
source /opt/aws/deepracer/lib/setup.bash


# Free /dev/video0 — AWS camera_node holds it but never publishes.
sudo pkill -f camera_node || true
sleep 1

cd "$(dirname "$0")"

# Config comes from .env (next to this script). See .env.example.
if [ ! -f .env ]; then
    echo "ERROR: car_bridge/.env not found. Copy .env.example and fill it in."
    exit 1
fi

python3 camera_publisher.py &
CAM_PID=$!
python3 command_subscriber.py &
CMD_PID=$!

trap "kill $CAM_PID $CMD_PID 2>/dev/null" EXIT
wait
