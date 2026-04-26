"""HTTP / WebSocket / MJPEG server for the Ghost Racer dashboard.

Exposes the live sim state (telemetry, frames, race control, training,
capture, MQTT pass-through) over uvicorn so the Next.js frontend at
web/ can render real data instead of mocks.

Entrypoint:  uvicorn ghost_racer.server.app:app --port 8000
"""
