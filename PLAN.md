# GHOST RACER — Implementation Plan

**Project:** Live behavioral cloning showdown — two AWS DeepRacers running cloned human driving policies against each other.
**Theme:** Clones (ACL Hacks 26)
**Goal:** Maximum technical-depth demo. Multiple ML/hardware systems composed into one coherent live show.

---

## The Demo (definition of "done")

A 3-act live demo:

1. **Act 1 — Capture.** Human stands at trackside, hand over a Leap Motion. Tilt = steering, height = throttle. DeepRacer #1 mirrors the hand in real time. A live dashboard shows: video feed from the car, the (steering, throttle) signal, and a "training data collected" counter ticking up with each lap.
2. **Act 2 — Clone.** Press a button. A behavioral-cloning model finishes training on the captured (image → action) pairs. DeepRacer #1 stops being teleoperated and drives **autonomously in the human's style** from camera input alone. The dashboard shows the loss curve and a "policy: HUMAN_A v1" badge.
3. **Act 3 — Clone Wars.** A second human's policy (already trained earlier in the day, or trained live on Car #2) is loaded onto DeepRacer #2. Both cars race autonomously. DeepLens overhead tracks them and renders a live leaderboard with lap times. Race-light tower (ESP32) signals start and winner.

**Hero shot:** Two cars racing, *no humans touching anything*, leaderboard updating live, both cars driving like the humans who trained them.

---

## Architecture

```
┌─────────────────┐    ┌──────────────────────────────────────┐
│  Leap Motion    │───▶│  Control Laptop (Python)              │
│  (USB → laptop) │    │  - LeapPipe: hand → (steer, throttle)│
└─────────────────┘    │  - DataRecorder: (frame, action) pairs│
                       │  - Trainer: PyTorch CNN policy        │
┌─────────────────┐    │  - PolicyServer: serves inference     │
│  DeepLens       │───▶│  - Dashboard: web UI (FastAPI + WS)   │
│  (overhead cam) │    └──────────────────────────────────────┘
└─────────────────┘            │           │             ▲
                               │ MQTT/WS   │ MQTT/WS     │
                               ▼           ▼             │
                       ┌────────────┐ ┌────────────┐     │
                       │ DeepRacer1 │ │ DeepRacer2 │─────┘ camera frames up,
                       │ - cam→up   │ │ - cam→up   │       commands down
                       │ - cmds←    │ │ - cmds←    │
                       └────────────┘ └────────────┘

ESP32 race-light tower ← MQTT (start/winner signals)
```

### Components

| Component | Tech | Owner |
|---|---|---|
| LeapPipe | Python + Leap SDK → normalized (steer, throttle) | ML/UX |
| Control bridge on car | Python service on DeepRacer, subscribes to commands, publishes camera frames | Hardware |
| Data recorder | Stores `(frame_jpeg, steer, throttle, ts)` to disk during teleop | ML |
| BC trainer | PyTorch, small CNN (ResNet18 or smaller), regression head | ML |
| Policy server | Loads trained model, accepts frames, returns actions; can run on laptop or onboard car | ML |
| DeepLens tracker | Onboard model → car bounding boxes; publish positions over MQTT | Vision |
| Leaderboard | Web dashboard, lap counting from positional crossings of a virtual finish line | Vision/UX |
| Race tower | ESP32 + 3 LEDs (red/yellow/green) + buzzer, MQTT subscriber | Hardware |

### Why MQTT
One broker (Mosquitto on the laptop), three topic groups: `car/{id}/cmd`, `car/{id}/frame`, `race/{event}`. Easy to debug with `mosquitto_sub -t '#' -v`. Falls back to plain WebSockets if MQTT trips us up.

---

## Milestones (with go/no-go gates)

### M0 — Hardware Liveness (target: hour 1–3)
**Gate: every device boots and is reachable.**
- [ ] Both DeepRacers boot, get IPs, accept SSH
- [ ] Leap Motion enumerates and yields hand frames in a Python script
- [ ] DeepLens streams MJPEG to laptop
- [ ] ESP32 flashes "hello world" servo + LED
- [ ] Mosquitto running on laptop, all devices reach it
- [ ] Laptop can ping each device by hostname

> If anything here fails by hour 4, **switch to fallback**: drop DeepLens (use per-car odometry for laps), or drop second DeepRacer (single-car ghost mode).

### M1 — Teleop Loop (hour 3–8)
**Gate: hand moves → car moves, and we record clean data.**
- [ ] Leap → (steer, throttle) calibrated mapping (with deadzone, smoothing)
- [ ] Control bridge on Car #1: receives MQTT cmd → drives motors
- [ ] Camera frames published from car at ≥10 fps
- [ ] Data recorder writes synchronized `(frame, action)` to disk
- [ ] Manual sanity check: drive a lap with hand, replay recorded frames

### M2 — Behavioral Cloning Trains (hour 8–14)
**Gate: model trained on a session can drive the same track.**
- [ ] Dataset loader, train/val split
- [ ] Small CNN policy (input: 84×84 or 120×160 RGB; output: 2 floats)
- [ ] Train script with logging (loss, action histograms)
- [ ] Inference server: receives frame, returns action, hits ≥20 Hz
- [ ] Closed-loop test on Car #1: model drives the track without human

### M3 — Two Clones, One Track (hour 14–20)
**Gate: two cars running two policies on the same track, simultaneously.**
- [ ] Train a second policy from a different human's demos
- [ ] Both cars run autonomous at the same time without colliding (start staggered)
- [ ] Per-car policy hot-swap from the dashboard

### M4 — Overhead Vision + Leaderboard (parallel track from M0; due hour 18)
**Gate: DeepLens reports car positions to the dashboard.**
- [ ] DeepLens model: detect each car (color tape on top of cars for ID)
- [ ] Position stream → laptop over MQTT
- [ ] Lap counting: detect crossing of virtual finish line
- [ ] Leaderboard UI updates live

### M5 — Polish & Demo Flow (hour 20–24)
- [ ] Race tower: red/yellow/green countdown, buzzer on race start, flash on winner
- [ ] Dashboard: training curve, lap times, live camera feeds, "policy badge" cards
- [ ] Run demo end-to-end at least 3 times back-to-back
- [ ] Backup: pre-trained policies on USB so a live training failure doesn't kill the demo

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| DeepRacer setup hell (image flashing, ROS, networking) | High | M0 is the gate; budget hour 0–3 for nothing else |
| BC policies don't generalize to track | Medium | Collect more demos; aggressive data augmentation (brightness, blur); reduce track speed |
| DeepLens detection unreliable | Medium | Color-tape car tops; fall back to onboard lap timing via known landmarks |
| Cars collide during clone-vs-clone | High | Staggered start; speed cap; recovery script that lifts both cars on collision |
| Wi-Fi at venue is bad | Medium-High | Bring our own travel router; everything on local network |
| Live training takes too long for the demo | Low | Pre-record demos in the morning; "live training" in the demo is a fine-tune, not from scratch |
| Leap Motion driver issues on Linux | Medium | Test laptop choice before event; have MediaPipe webcam fallback for hand tracking |

---

## Stretch Goals (only if M0–M5 are green by hour 18)

- **Style indicator:** Show a 2D embedding of policy behavior so judges can see "human A drives smooth, human B drives aggressive."
- **Live retraining:** Mid-race, take over Car #1 with Leap, demonstrate new behaviors, retrain online, redeploy.
- **Adversarial clone:** Train a policy with an objective to "block" the other car (basic RL fine-tune over BC base).
- **Voice clone narration:** Claude + TTS commentates the race in real time.

---

## Team Split (assuming 3 people)

- **Hardware / Robotics** — Owns M0 entirely, M1 control bridge, M5 race tower. Critical-path early.
- **ML** — M1 data recorder, M2 trainer + inference, M3 two-policy orchestration.
- **Vision / UX** — M4 DeepLens + leaderboard, dashboard UI throughout, demo flow.

Daily syncs: end of M0, end of M2, end of M4. If a milestone slips by >2 hours, regroup and cut scope.

---

## Demo Script (for the judges, ~3 minutes)

1. *"This is Alice. Watch her drive a car with her hand."* — Act 1, 30s.
2. *"That hand-driving was training a neural network in real time. Now Alice steps back."* — Act 2, 30s. Car drives solo.
3. *"Bob did the same earlier. Two humans, two clones. They've never raced each other — until now."* — Act 3, 90s. Cars race, leaderboard updates, race tower flashes the winner.
4. *"Every part of this — the gesture capture, the live training, the overhead tracking, the autonomous racing — is built from scratch this weekend."* — close.

---

## Open Questions

- Which laptop runs the broker + training? (Needs a GPU ideally — confirm.)
- DeepRacer firmware version on each car? (Affects ROS API.)
- Can we mount DeepLens overhead, or is it tripod-only? (Affects FOV.)
- Track shape — oval, figure-8, or curved? (Affects how forgiving BC needs to be.)
