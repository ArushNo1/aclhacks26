"""FastAPI app exposing the Ghost Racer sim to the Next.js dashboard.

Run:
    uvicorn ghost_racer.server.app:app --port 8000 --reload

Endpoints:
  GET  /api/status                  one-shot snapshot
  POST /api/race/start              kick off lights -> green
  POST /api/race/reset              stop race, idle phase
  POST /api/policy/active           {"name": "bc"|"rl"|"none"}
  POST /api/policy/reload           reload BC weights from disk
  GET  /api/leaderboard             [{name,best_lap_s,laps}, ...]
  GET  /api/health                  device-style metrics for Act 4
  POST /api/capture/start           begin recording (writes .npz on stop)
  POST /api/capture/stop            persist + return path
  POST /api/train/start             {"epochs"?:int} kick off background BC training
  POST /api/train/stop              best-effort cancel (training is single-threaded)
  WS   /ws/telemetry                20 Hz JSON pushes of full SimState
  WS   /ws/mqtt                     pass-through of car/+/+ messages
  GET  /stream/spectator.mjpg       multipart/x-mixed-replace top-down view
  GET  /stream/player.mjpg          240x320 player 3D view
  GET  /stream/ai.mjpg              120x160 policy obs (the AI's eyes)
"""
from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from .mjpeg import BOUNDARY, mjpeg_stream
from .sim_runner import SimRunner
from .state import SimState


_state: Optional[SimState] = None
_runner: Optional[SimRunner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _state, _runner
    _state = SimState()
    _runner = SimRunner(_state)
    app.state.sim_state = _state
    app.state.sim_runner = _runner

    # Mqtt + capture/train integrations are wired lazily inside the runner.
    await _runner.start()
    try:
        # Try the MQTT bridge but don't fail startup if the broker is down.
        from .mqtt_bridge import MqttBridge
        bridge = MqttBridge()
        await bridge.start()
        app.state.mqtt_bridge = bridge
    except Exception as e:
        print(f"[server] mqtt bridge disabled: {e}")
        app.state.mqtt_bridge = None

    yield

    if app.state.mqtt_bridge is not None:
        await app.state.mqtt_bridge.stop()
    await _runner.stop()


app = FastAPI(lifespan=lifespan, title="Ghost Racer Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------- helpers
def _state_obj() -> SimState:
    s = app.state.sim_state
    if s is None:
        raise HTTPException(status_code=503, detail="sim not started")
    return s


def _runner_obj() -> SimRunner:
    r = app.state.sim_runner
    if r is None:
        raise HTTPException(status_code=503, detail="sim not started")
    return r


# -------------------------------------------------------------------- REST
@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    return _state_obj().snapshot()


class PolicyPayload(BaseModel):
    name: str  # 'bc' | 'rl' | 'none'


@app.post("/api/policy/active")
async def set_policy(p: PolicyPayload) -> Dict[str, Any]:
    runner = _runner_obj()
    try:
        runner.set_active_policy(p.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"policy_active": p.name}


@app.post("/api/policy/reload")
async def reload_policy() -> Dict[str, Any]:
    runner = _runner_obj()
    version = runner.reload_bc()
    if version is None:
        raise HTTPException(status_code=404, detail="no bc_policy.pt on disk")
    return {"policy_version": version}


@app.post("/api/race/start")
async def race_start() -> Dict[str, Any]:
    runner = _runner_obj()
    await runner.start_race()
    return {"started": True}


@app.post("/api/race/reset")
async def race_reset() -> Dict[str, Any]:
    runner = _runner_obj()
    runner.reset_race()
    return {"reset": True}


@app.get("/api/leaderboard")
async def leaderboard() -> Dict[str, Any]:
    s = _state_obj().snapshot()
    rows = []
    for slot, key in (("car1", "car1"), ("car2", "car2")):
        c = s["race"][key]
        rows.append({
            "name": slot,
            "laps": c["lap_count"],
            "best_lap_s": c["best_lap_s"],
            "last_lap_s": c["last_lap_s"],
        })
    rows.sort(key=lambda r: (-r["laps"], r["best_lap_s"] or float("inf")))
    return {"rows": rows}


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    """Device-style health rows for Act 4 (psutil-driven, plus runner meta)."""
    try:
        import psutil  # noqa: WPS433
    except Exception:
        psutil = None  # type: ignore[assignment]

    rows = []
    if psutil is not None:
        rows.append({
            "name": "Sim host",
            "sub": "localhost",
            "metrics": {
                "CPU": f"{int(psutil.cpu_percent(interval=None))}%",
                "RAM": f"{int(psutil.virtual_memory().percent)}%",
                "LOADAVG": f"{os.getloadavg()[0]:.2f}",
            },
        })
    state = _state_obj()
    snap = state.snapshot()
    rows.append({
        "name": "Sim runner",
        "sub": f"tick #{snap['tick']}",
        "metrics": {
            "FPS": f"{snap['fps']:.1f}",
            "PHASE": snap["phase"].upper(),
            "POLICY": snap["policy_active"].upper(),
        },
    })
    bridge = app.state.mqtt_bridge
    rows.append({
        "name": "MQTT broker",
        "sub": bridge.broker_url() if bridge is not None else "(disabled)",
        "metrics": {
            "STATUS": bridge.status() if bridge is not None else "OFF",
            "MSG/S": f"{bridge.msg_rate():.1f}" if bridge is not None else "0",
            "CLIENTS": str(bridge.client_count()) if bridge is not None else "0",
        },
    })
    return {"devices": rows}


# ----------------------------------------------- capture (Act 1)
@app.post("/api/capture/start")
async def capture_start() -> Dict[str, Any]:
    runner = _runner_obj()
    from ..agent.recorder import SessionRecorder
    runner.recorder = SessionRecorder(runner.data_dir)
    sid = f"session_{int(time.time())}"
    started_at = time.time()
    with runner.state.lock():
        runner.state.capture.recording = True
        runner.state.capture.session_id = sid
        runner.state.capture.started_at = started_at
        runner.state.capture.frames = 0
        runner.state.phase = "capture"
    return {"session_id": sid, "started_at": started_at}


@app.post("/api/capture/stop")
async def capture_stop() -> Dict[str, Any]:
    runner = _runner_obj()
    rec = runner.recorder
    runner.recorder = None
    path = rec.save() if rec is not None else ""
    with runner.state.lock():
        sid = runner.state.capture.session_id
        runner.state.capture.recording = False
        runner.state.capture.last_save_path = path or None
        runner.state.phase = "idle"
        runner.state.capture.session_id = None
    return {
        "session_id": sid,
        "frames": (len(rec) if rec is not None else 0),
        "path": path,
    }


# ----------------------------------------------- train (Act 2)
class TrainPayload(BaseModel):
    epochs: Optional[int] = 8


@app.post("/api/train/start")
async def train_start(p: TrainPayload) -> Dict[str, Any]:
    """Kick off background BC training. Polls weight changes via the runner's
    reload_bc() once the trainer flips pending_reload."""
    runner = _runner_obj()
    if runner.training_manager is None:
        # Lazy import — pulls torch
        from ..play import TrainingManager
        runner.training_manager = TrainingManager(
            runner.data_dir, runner.bc_policy_path, epochs=int(p.epochs or 8)
        )
    tm = runner.training_manager
    tm.epochs = int(p.epochs or tm.epochs)
    started = tm.maybe_start()
    with runner.state.lock():
        runner.state.training.running = tm.training
        runner.state.training.total_epochs = tm.epochs
        runner.state.training.last_status = tm.last_status
        runner.state.phase = "training"
        if started:
            # Fresh run — clear the previous chart so progress starts at 0.
            runner.state.training.loss_points = []
            runner.state.training.current_epoch = 0
            runner.state.training.current_loss = 0.0
    # The TrainingManager reports "pending_reload" when finished;
    # we poll it from the periodic train-status pump below.
    asyncio.create_task(_train_pump())
    return {"started": started, "epochs": tm.epochs}


@app.post("/api/train/stop")
async def train_stop() -> Dict[str, Any]:
    runner = _runner_obj()
    tm = runner.training_manager
    if tm is None:
        return {"running": False}
    # TrainingManager does not support cancel; we just mark the desired state.
    with runner.state.lock():
        runner.state.training.last_status = tm.last_status
        runner.state.training.running = tm.training
        if not tm.training:
            runner.state.phase = "idle"
    return {"running": tm.training}


async def _train_pump() -> None:
    """Background poller that mirrors TrainingManager state into SimState
    until training finishes. Exits when the trainer is done and the policy
    has been hot-reloaded."""
    runner = _runner_obj()
    tm = runner.training_manager
    if tm is None:
        return
    while True:
        await asyncio.sleep(0.5)
        if tm is None:
            return
        new_epochs = tm.drain_epochs()
        with runner.state.lock():
            runner.state.training.running = tm.training
            runner.state.training.last_status = tm.status_line()
            for epoch, train_loss, _val_loss in new_epochs:
                runner.state.training.loss_points.append(float(train_loss))
                runner.state.training.current_epoch = epoch
                runner.state.training.current_loss = float(train_loss)
        if tm.pending_reload:
            runner.reload_bc()
            tm.pending_reload = False
            with runner.state.lock():
                runner.state.phase = "idle"
            return
        if not tm.training and tm.last_val_mse is None and tm.last_status.startswith("BC failed"):
            with runner.state.lock():
                runner.state.phase = "idle"
            return


# -------------------------------------------------------------------- WebSocket
@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket) -> None:
    await ws.accept()
    state = _state_obj()
    queue = state.subscribe()
    try:
        # Push a snapshot immediately so the client paints fast
        await ws.send_json(state.snapshot())
        while True:
            snap = await queue.get()
            await ws.send_json(snap)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        state.unsubscribe(queue)


@app.websocket("/ws/mqtt")
async def ws_mqtt(ws: WebSocket) -> None:
    await ws.accept()
    bridge = app.state.mqtt_bridge
    if bridge is None:
        await ws.send_json({"error": "mqtt bridge not running"})
        await ws.close()
        return
    queue = bridge.subscribe()
    try:
        while True:
            msg = await queue.get()
            await ws.send_json(msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        bridge.unsubscribe(queue)


# -------------------------------------------------------------------- MJPEG
def _mjpeg_response(frame_src) -> StreamingResponse:
    return StreamingResponse(
        mjpeg_stream(frame_src),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
        headers={
            "Cache-Control": "no-cache, private",
            "Pragma": "no-cache",
            "Connection": "close",
        },
    )


@app.get("/stream/spectator.mjpg")
async def spectator_mjpg() -> StreamingResponse:
    runner = _runner_obj()
    return _mjpeg_response(lambda: runner.last_spectator)


@app.get("/stream/player.mjpg")
async def player_mjpg() -> StreamingResponse:
    runner = _runner_obj()
    return _mjpeg_response(lambda: runner.last_player_view)


@app.get("/stream/ai.mjpg")
async def ai_mjpg() -> StreamingResponse:
    runner = _runner_obj()
    return _mjpeg_response(lambda: runner.last_ai_view)


# ----------------------------------------------- hand calibration (Act 1)
def _hand():
    runner = _runner_obj()
    h = runner.hand_runner
    if h is None or not h.attached:
        raise HTTPException(
            status_code=503,
            detail="hand capture unavailable (no webcam attached on the server host)",
        )
    return h


@app.get("/api/hand/status")
async def hand_status() -> Dict[str, Any]:
    runner = _runner_obj()
    h = runner.hand_runner
    if h is None:
        return {"attached": False, "error": "hand runner not initialised"}
    return {
        "attached": h.attached,
        "error": h.error,
        "calibrated": (
            bool(h.controller.calibration.has_arm_data) if h.controller is not None else False
        ),
        "calibration": h._calibration_dict() if h.controller is not None else None,
    }


@app.post("/api/hand/calibrate/start")
async def hand_calibrate_start() -> Dict[str, Any]:
    return _hand().start_calibration()


@app.post("/api/hand/calibrate/capture")
async def hand_calibrate_capture() -> Dict[str, Any]:
    return _hand().capture_step()


@app.post("/api/hand/calibrate/redo")
async def hand_calibrate_redo() -> Dict[str, Any]:
    return _hand().redo_step()


@app.post("/api/hand/calibrate/cancel")
async def hand_calibrate_cancel() -> Dict[str, Any]:
    return _hand().cancel_calibration()


@app.post("/api/hand/reset")
async def hand_reset() -> Dict[str, Any]:
    return _hand().reset_calibration()


@app.get("/stream/hand.mjpg")
async def hand_mjpg() -> StreamingResponse:
    """The webcam frame with the controller's overlay (pivot rings, hand
    size circles, side gauges). Browsers render via <img src=...>."""
    runner = _runner_obj()
    h = runner.hand_runner

    def _frame():
        if h is None or not h.attached:
            return None
        return h.last_overlay_frame  # already BGR

    # The overlay frame is BGR from cv2; do not re-swap.
    from fastapi.responses import StreamingResponse as _SR
    from .mjpeg import BOUNDARY as _B, mjpeg_stream as _ms
    return _SR(
        _ms(_frame, swap_rgb_to_bgr=False),
        media_type=f"multipart/x-mixed-replace; boundary={_B}",
        headers={
            "Cache-Control": "no-cache, private",
            "Pragma": "no-cache",
            "Connection": "close",
        },
    )


@app.get("/")
async def root():
    return JSONResponse({"name": "ghost-racer-server", "status": "ok"})
