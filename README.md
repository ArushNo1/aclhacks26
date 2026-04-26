# 67 RACER

Live behavioral-cloning showdown on AWS DeepRacers. Drive a car with your hand
over a webcam (or Leap Motion), train a neural-net policy on the demonstrations,
then watch your clone race a teammate's clone autonomously — built for
ACL Hacks 26 (theme: **Clones**).

The full demo arc:

1. **Capture.** Hand over the camera → steering + throttle. The car (or sim)
   mirrors your hand and records `(frame, action)` pairs.
2. **Clone.** A small CNN trains on the captured pairs. The car drops teleop
   and drives autonomously *in the human's style* from camera input alone.
3. **Clone Wars.** Two policies — yours and a teammate's — race head-to-head
   while a Next.js dashboard shows live telemetry, lap times, and a leaderboard.

## Repo layout

| Path | What lives there |
|---|---|
| [ghost_racer/](ghost_racer/) | Python package: sim, BC/RL training, FastAPI server, hand controller, demo entry point |
| [ghost_racer/sim/](ghost_racer/sim/) | Top-down race-car gym env with domain randomization |
| [ghost_racer/agent/](ghost_racer/agent/) | `PolicyCNN`, BC and RL trainers, session recorder |
| [ghost_racer/server/](ghost_racer/server/) | FastAPI + WebSocket + MJPEG server that powers the dashboard |
| [ghost_racer/control/](ghost_racer/control/) | Hand-tracking → `(steer, throttle)` controller |
| [ghost_racer/deepracer_export/](ghost_racer/deepracer_export/) | PyTorch → ONNX export for on-car inference |
| [car_bridge/](car_bridge/) | Runs **on the DeepRacer**: MQTT ↔ ROS 2 bridge for camera frames + motor commands |
| [laptop/](laptop/) | Laptop-side helpers: hand-drive, record real-car data, view frames, smoke test motors |
| [leap_demo/](leap_demo/) | Standalone Leap Motion / webcam hand demos |
| [web/](web/) | Next.js 16 dashboard (live leaderboard, telemetry, policy controls) |

Planning + context: [PLAN.md](PLAN.md), [IDEAS.md](IDEAS.md), [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md).

## Quickstart (sim only, no hardware)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Drive the sim with your hand, train BC inline:
python -m ghost_racer.play --record --auto-train

# Or run the dashboard server + Next.js UI:
uvicorn ghost_racer.server.app:app --port 8000 --reload
cd web && npm install && npm run dev   # http://localhost:3000
```

Hotkeys in the pygame window: `1` BC policy · `2` RL policy · `0` cruise ·
`R` reset · `S` save recording · `Q`/`ESC` quit.

## Running on real DeepRacers

The car runs the bridge in [car_bridge/](car_bridge/); the laptop runs Mosquitto
and the policy server. Full setup (firewall, broker, ROS quirks, MQTT topics)
is in [car_bridge/README.md](car_bridge/README.md).

MQTT topics:

| Topic | Direction | Payload |
|---|---|---|
| `car/{id}/frame` | car → laptop | raw JPEG bytes |
| `car/{id}/cmd`   | laptop → car | JSON `{"steer": -1..1, "throttle": -1..1}` |
| `race/{event}`   | bidirectional | race-tower / leaderboard events |

## Stack

- **ML:** PyTorch, Stable-Baselines3, ONNX Runtime
- **Sim / control:** Gymnasium, pygame, OpenCV, MediaPipe
- **Realtime glue:** Mosquitto (MQTT), `paho-mqtt`, FastAPI WebSockets
- **Hardware:** AWS DeepRacer (ROS 2), AWS DeepLens (overhead vision),
  Leap Motion / webcam, ESP32 race-light tower
- **Frontend:** Next.js 16 + React 19 + Tailwind 4

## Notes for contributors

- This repo uses **Next.js 16** — APIs, conventions, and file structure differ
  from older versions. See `node_modules/next/dist/docs/` before writing UI
  code, and heed deprecation notices.
- Heavy imports (`torch`, `gymnasium`, `stable_baselines3`) in
  [ghost_racer/play.py](ghost_racer/play.py) are deliberately deferred so the
  hand-calibration window opens fast — keep it that way.
- The DeepRacer's stock `camera_node` grabs `/dev/video0` but never publishes;
  [car_bridge/start_bridge.sh](car_bridge/start_bridge.sh) kills it before
  starting our publisher. The rest of `deepracer-core` (`ctrl_pkg`, `servo_pkg`)
  must keep running.

## License

[MIT](LICENSE).
