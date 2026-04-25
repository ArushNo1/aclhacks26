# Clone-Themed Hackathon Ideas

Ranked roughly by "demo wow" × "feasibility in a hackathon."

---

## Tier S — Hero demos

### 1. **Mirror, Mirror** — Your DeepRacer Clone
**Hardware:** Leap Motion + DeepRacer + (optional) ESP32 haptic wristband
**Pitch:** You "drive" with your hand in the air via Leap Motion. The DeepRacer records your trajectories, then *clones your driving style* via behavioral cloning. Press a button — the car drives like you, including your quirks (do you drift? hesitate at corners?). Side-by-side: "you" vs "your clone" lap time.
**Hero moment:** A second run where the car solo-drives a track in your style, and a third where multiple cloned policies (yours vs teammate's) race head-to-head.
**Risk:** Behavioral cloning needs decent demonstrations; track must be controlled.

### 2. **Puppet Master** — Gesture-Cloned Animatronic
**Hardware:** Leap Motion + ESP32 + servos (a small animatronic hand/face)
**Pitch:** Leap captures your hand. ESP32 drives servos that mirror it in real time — your physical clone. Add a "record" mode that saves a 10s gesture loop and lets the clone perform autonomously while you walk away. Bonus: chain multiple puppets that all clone the same input.
**Hero moment:** You wave goodbye, walk away, and the puppet keeps waving at the next person who approaches (DeepLens detects them).
**Risk:** Servo jitter; latency budget is tight but doable.

### 3. **Are You The Real One?** — Deepfake Detector Booth
**Hardware:** DeepLens + Leap Motion (liveness check) + ESP32 (visual verdict: green/red light)
**Pitch:** A booth that decides if you're a "clone" (deepfake/photo) or real. DeepLens runs face detection + liveness; Leap confirms a hand is physically present in 3D space (a photo can't fake that). ESP32 lights up GREEN/RED with dramatic flair. Optional: it tries to *clone you* (snap face, swap into a meme) when it detects you're real.
**Hero moment:** Hold a printed photo of a teammate up — booth says CLONE DETECTED. Stand in front normally — REAL HUMAN VERIFIED.
**Risk:** Lighting; train liveness on quick local data.

---

## Tier A — Strong contenders

### 4. **Clone Wars** — Multi-Agent Behavioral Cloning Race
**Hardware:** 2+ DeepRacers, DeepLens overhead
**Pitch:** Each team member records their driving style. Clone policies are deployed onto separate cars. The cars race each other on the same track — a literal "clone war." DeepLens above the track tracks lap positions and broadcasts a leaderboard.
**Hero moment:** Live leaderboard while ghosts of human drivers battle.
**Risk:** Need ≥2 working DeepRacers and a track.

### 5. **Voice Clone Turing Test**
**Hardware:** Mostly software, but DeepLens for "audience reaction cam," ESP32 buzzer for verdict
**Pitch:** Audience hears 3 voice clips of the same sentence. One is a teammate; two are AI clones (different models). Audience votes via QR code. Track which voice tech is most convincing. Simple, social, hilarious.
**Hero moment:** Reveal moment with crowd reactions.
**Risk:** Light on hardware integration — may not feel "hardware-y" enough.

### 6. **Shadow Driver** — Follow-the-Leader DeepRacer
**Hardware:** 2 DeepRacers (one leader, one clone)
**Pitch:** Lead DeepRacer is teleoperated (or driving a recorded path). Second DeepRacer clones the leader's behavior using vision-based following — its camera locks onto the lead car and matches steering/speed. Shadowing in formation.
**Hero moment:** Tight S-curve where the shadow car perfectly tails the leader.
**Risk:** Vision tracking under bad lighting.

### 7. **Gesture-Cloned Drone Swarm (DeepRacer Edition)**
**Hardware:** Leap Motion + multiple DeepRacers
**Pitch:** Your hand controls a swarm. Each finger maps to a car. Move your hand — they fan out, regroup, follow your gesture as a formation. "Conducting" a clone army with your hands.
**Hero moment:** Pinch fingers together → cars converge. Spread → fan out.
**Risk:** Coordinated multi-car control is fiddly; needs reliable wifi.

---

## Tier B — Clever but smaller scope

### 8. **DeepLens Memory** — Clone-of-the-Day
DeepLens watches the hackathon all day, picks the most "memorable" person via clustering of detected faces + activity, and at the end generates a stylized "clone" profile. Ambient art piece.

### 9. **The Impersonator** — LLM clone of a person
Train a Claude prompt on a teammate's Slack/messages. Build a chatbot that mimics them. Add a Leap-Motion-controlled "talk to your clone" puppet head (ESP32 servos for mouth open/close synced to TTS). Dual hardware/software hit.

### 10. **Twin Trajectories** — Forking-reality DeepRacer
DeepRacer drives a track. At each decision point (intersection), it "forks" — visualization shows N parallel clones taking different paths in a digital twin, while the real car commits to one. Multiverse-themed UI.

### 11. **Echo Chamber** — Audio clone amplifier
ESP32 mics around a room. They pick up phrases and play them back later in different teammates' voice clones. Surreal art / social experiment piece.

---

## Recommended Day-1 Path

1. **Pick 1 Tier-S idea** as the hero, plus a Tier-B fallback if hardware bricks.
2. **De-risk hardware first** — boot the DeepRacer, plug in Leap, flash an ESP32 with a hello-world servo/LED, get DeepLens streaming. Don't write app logic until each piece is alive.
3. **Define the hero moment in one sentence** before coding. Build toward that shot.
4. **Two tracks in parallel:** one person on hardware integration, one on the ML/software clone behavior.

---

## Open Questions for the Team

- How many DeepRacers do we have working? (1 vs 2+ unlocks Tier A ideas)
- Do we have a track / open floor space for car demos?
- How many Leap Motions? (1 is fine; 2 enables "duel" interactions)
- Any displays / projectors for visualization?
- Are we judged on novelty, polish, or technical depth? (changes idea pick)
