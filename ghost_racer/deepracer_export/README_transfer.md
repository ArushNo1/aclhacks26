# Transfer to a real AWS DeepRacer

The simulator and the car share the same action contract: a 2-vector in
`[-1, 1]` for `(steer_norm, throttle_norm)`, scaled to physical units using
`MAX_STEER_RAD` and `MAX_SPEED_MPS` (defined in [ghost_racer/sim/car.py](../sim/car.py)).
Both BC and RL export to the same ONNX format, so on-car code is identical
regardless of which policy you trained.

## Files produced by the exporter

`python -m ghost_racer.deepracer_export.to_onnx --mode {bc,rl} --ckpt <pt|zip> --out policy.onnx`

- `policy.onnx` — the network. Input `(B, 3, H, W)` float32 in `[0, 1]`. Output `(B, 2)` in `[-1, 1]`.
- `policy_info.json` — input shape, `max_steer_rad`, `max_throttle_mps`, preprocessing notes.

## On-car loop (pseudocode)

```python
import onnxruntime as ort, cv2, numpy as np, json

info = json.load(open("policy_info.json"))
H, W = info["input_shape"][1], info["input_shape"][2]
sess = ort.InferenceSession("policy.onnx")

while True:
    frame = camera.read()                              # ROS topic /camera/image_raw
    img = cv2.resize(frame, (W, H))[..., ::-1]         # BGR->RGB
    x = img.astype(np.float32).transpose(2, 0, 1) / 255.0
    a = sess.run(None, {"obs": x[None, ...]})[0][0]    # (steer_norm, throttle_norm)

    steer_rad = float(np.clip(a[0], -1, 1)) * info["max_steer_rad"]
    speed_mps = float(np.clip(a[1], -1, 1)) * info["max_throttle_mps"]

    publish_servo(steer_rad)                           # /servo_msgs/raw_pwm
    publish_throttle(speed_mps)
```

## Sim2real checklist

- [ ] Train with `--domain-rand` so the CNN tolerates lighting/color shifts.
- [ ] Match the camera resize: same `(H, W)` and BGR→RGB conversion as in this README.
- [ ] On the car, **rate-limit the loop to ~20 Hz** to match the sim `dt=0.05`.
- [ ] If the car drifts straight, the throttle scaling is too high — lower
      `MAX_SPEED_MPS` in `sim/car.py` and retrain (or scale `speed_mps` down at runtime).
- [ ] If the car oversteers, lower `MAX_STEER_RAD` similarly.
- [ ] Keep a kill-switch publisher that zeros throttle if the inference loop drops.

## Why the ONNX approach (vs SageMaker / RoboMaker)

The official DeepRacer toolchain uses SageMaker RL + RoboMaker for full
training pipelines. We bypass that for two reasons:

1. **Hackathon time budget.** The full pipeline takes hours to provision and
   debug. ONNX is one file dropped onto the car.
2. **Same artifact runs anywhere.** The same `policy.onnx` runs on the
   DeepRacer's onboard Atom CPU, on a tethered laptop pushing commands over
   MQTT, or back in the simulator for replay.
