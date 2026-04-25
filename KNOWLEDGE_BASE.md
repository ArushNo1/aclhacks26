# ACL Hacks 26 — Hackathon Knowledge Base

**Theme:** Clones
**Date:** 2026-04-25

---

## Hardware Inventory

### AWS DeepRacer
- 1/18th scale autonomous race car
- Onboard compute: Intel Atom (Ubuntu), ROS-based stack
- Front-facing camera (stereo on newer models), optional LIDAR
- Wi-Fi connected, SSH-able, runs custom inference models
- Best for: real-world physical agent, RL demos, follow-the-leader, swarm/clone behaviors

### AWS DeepLens
- Deep-learning-enabled video camera
- Onboard inference (Intel GPU), runs MXNet/TensorFlow models
- Streams MJPEG, integrates with AWS Lambda/Greengrass
- Best for: vision tasks at the edge — face/pose/object recognition, gesture triggers

### Leap Motion Sensor(s)
- Hand/finger tracking (sub-millimeter), ~150° FOV, USB-tethered
- SDK exposes 3D skeleton of both hands at ~120fps
- Best for: gesture control, mocap, "puppet your clone" interactions

### Arduino / ESP Kits
- ESP32 + Arduino Uno/Nano variants
- Wi-Fi/Bluetooth (ESP32), GPIO, I2C, common sensors/actuators
- Servos, LEDs, buttons, possibly displays
- Best for: physical output (animatronics, lights, haptics), distributed sensors, glue between digital + real world

---

## Theme: "Clones"

Interpretations to mine for ideas:
- **Identity copy** — make a digital twin of a person (voice, face, gestures, behavior)
- **Behavioral cloning** — ML technique: imitate demonstrations (perfect for DeepRacer)
- **Swarm / multiplicity** — many copies of one agent acting together or in formation
- **Mirror / shadow** — a clone that mimics you in real-time
- **Impersonation / deepfake-aware** — detect clones, verify humanity
- **Forking reality** — branching versions of the same scene/agent
- **Clone wars** — adversarial copies competing

---

## Software Stack (recommended)

- **Vision/ML:** Python, PyTorch, OpenCV, MediaPipe (for backup hand/pose)
- **LLM/agent glue:** Anthropic SDK (Claude), available locally
- **Realtime:** WebSockets / MQTT for orchestrating DeepRacer + ESP32 + UI
- **Frontend:** React/Next.js or simple HTML for demo dashboards
- **Voice:** Whisper (STT), ElevenLabs / local TTS for voice cloning
- **Face/pose:** MediaPipe, InsightFace, or DeepLens-native models

---

## Idea Brainstorm

See `IDEAS.md` for ranked concepts.

---

## Constraints / Reality Check

- Hackathon time budget — favor ideas with a clear demoable hero moment
- Hardware integration is where things break — prototype the riskiest hardware path first
- Wi-Fi at venues is unreliable — prefer local network / hotspot setups
- DeepRacer setup has historical pain (image flashing, ROS) — verify it boots Day 1
