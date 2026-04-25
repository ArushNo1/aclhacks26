"use client";

import { useEffect, useRef, useState } from "react";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

type SimFrame = {
  spectator: string;
  ai_fp: string;
  hand_fp: string;
  lap_ego: number;
  lap_opp: number;
  steer: number;
  throttle: number;
  has_hand: boolean;
  off_track: boolean;
  collision: boolean;
  ego_progress: number;
  opp_progress: number;
  fps: number;
  policy: string;
};

function Bar({
  label,
  value,
  color = "bg-cyan-500",
  signed = false,
}: {
  label: string;
  value: number;
  color?: string;
  signed?: boolean;
}) {
  const pct = signed
    ? Math.abs(value) * 100
    : Math.max(0, Math.min(1, value)) * 100;
  const side = signed && value < 0 ? "right" : "left";

  return (
    <div className="flex items-center gap-3">
      <span className="w-14 font-mono text-xs text-zinc-500">{label}</span>
      <div className="relative h-2 flex-1 rounded-full bg-zinc-800">
        {signed ? (
          <>
            <div className="absolute inset-y-0 left-1/2 w-px bg-zinc-600" />
            <div
              className={`absolute inset-y-0 rounded-full ${color}`}
              style={{
                [side]: "50%",
                width: `${pct / 2}%`,
              }}
            />
          </>
        ) : (
          <div
            className={`absolute inset-y-0 left-0 rounded-full ${color}`}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      <span className="w-12 text-right font-mono text-xs text-zinc-300">
        {value >= 0 ? "+" : ""}
        {value.toFixed(2)}
      </span>
    </div>
  );
}

function NotConnected() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-4 pt-16">
      <div className="text-center">
        <div className="mb-4 font-mono text-xs font-bold tracking-widest text-zinc-600">
          CONNECTION
        </div>
        <div className="mb-2 font-mono text-4xl font-black text-zinc-700">
          OFFLINE
        </div>
        <p className="text-sm text-zinc-600">
          The Python simulation server is not running.
        </p>
      </div>

      <div className="w-full max-w-lg rounded-lg border border-zinc-800 bg-zinc-950 p-6">
        <div className="mb-3 font-mono text-xs font-bold tracking-widest text-cyan-500">
          START THE SERVER
        </div>
        <pre className="overflow-x-auto rounded bg-black p-4 font-mono text-sm text-green-400">
          {`cd /home/arush/aclhacks26\npip install fastapi "uvicorn[standard]" websockets\npython -m ghost_racer.ws_server`}
        </pre>
        <p className="mt-3 font-mono text-xs text-zinc-600">
          Then refresh this page. Connecting to{" "}
          <span className="text-zinc-400">{WS_URL}</span>
        </p>
      </div>
    </div>
  );
}

export default function SimDemo() {
  const [connected, setConnected] = useState(false);
  const [frame, setFrame] = useState<SimFrame | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        // retry after 2 s
        setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (e: MessageEvent) => {
        setFrame(JSON.parse(e.data) as SimFrame);
      };
    }

    connect();
    return () => {
      wsRef.current?.close();
    };
  }, []);

  if (!connected || !frame) {
    return <NotConnected />;
  }

  const progressBarEgo = Math.min(1, (frame.ego_progress % 1));
  const progressBarOpp = Math.min(1, (frame.opp_progress % 1));

  return (
    <div className="flex min-h-screen flex-col bg-black pt-0">
      {/* Status bar */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-6 py-3">
        <a href="/" className="font-mono text-sm font-black tracking-widest text-white hover:text-cyan-400 transition-colors">
          ← GHOST RACER
        </a>
        <div className="flex items-center gap-4">
          <span className="font-mono text-xs text-zinc-500">
            POLICY:{" "}
            <span className="text-cyan-400">{frame.policy}</span>
          </span>
          <span className="font-mono text-xs text-zinc-500">
            {frame.fps.toFixed(1)} FPS
          </span>
          {frame.collision && (
            <span className="rounded bg-red-500/20 px-2 py-0.5 font-mono text-xs font-bold text-red-400">
              COLLISION
            </span>
          )}
          {frame.off_track && (
            <span className="rounded bg-yellow-500/20 px-2 py-0.5 font-mono text-xs font-bold text-yellow-400">
              OFF TRACK
            </span>
          )}
          <span className="flex items-center gap-1.5 font-mono text-xs font-bold text-green-400">
            <span className="animate-pulse">●</span> LIVE
          </span>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col gap-4 p-4 lg:flex-row">
        {/* Left: spectator view */}
        <div className="flex flex-col gap-2">
          <div className="font-mono text-xs font-bold tracking-widest text-zinc-500">
            SPECTATOR VIEW
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`data:image/jpeg;base64,${frame.spectator}`}
            alt="spectator"
            className="w-full rounded-lg border border-zinc-800 lg:w-[500px]"
            style={{ imageRendering: "pixelated" }}
          />
        </div>

        {/* Right: cameras + telemetry */}
        <div className="flex flex-1 flex-col gap-4">
          {/* Camera row */}
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <div className="font-mono text-xs font-bold tracking-widest text-zinc-500">
                AI CAMERA
              </div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`data:image/jpeg;base64,${frame.ai_fp}`}
                alt="AI first-person view"
                className="w-full rounded-lg border border-cyan-500/20"
                style={{ imageRendering: "pixelated" }}
              />
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 font-mono text-xs font-bold tracking-widest text-zinc-500">
                HAND CAM
                {frame.has_hand && (
                  <span className="text-green-400">● TRACKING</span>
                )}
              </div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`data:image/jpeg;base64,${frame.hand_fp}`}
                alt="hand camera"
                className="w-full rounded-lg border border-green-500/20"
              />
            </div>
          </div>

          {/* Telemetry */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
            <div className="mb-3 font-mono text-xs font-bold tracking-widest text-zinc-500">
              TELEMETRY
            </div>
            <div className="flex flex-col gap-3">
              <Bar
                label="STEER"
                value={frame.steer}
                color="bg-cyan-500"
                signed
              />
              <Bar
                label="THRTL"
                value={frame.throttle}
                color="bg-green-500"
              />
            </div>
          </div>

          {/* Car cards */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-cyan-500/25 bg-zinc-950 p-4">
              <div className="mb-3 flex items-center justify-between">
                <span className="font-mono text-xs font-bold tracking-widest text-cyan-400">
                  CAR A — AI
                </span>
              </div>
              <div className="mb-3">
                <div className="mb-1 font-mono text-xs text-zinc-500">LAPS</div>
                <div className="font-mono text-3xl font-black text-white">
                  {frame.lap_ego}
                </div>
              </div>
              <div>
                <div className="mb-1 flex justify-between font-mono text-xs text-zinc-500">
                  <span>PROGRESS</span>
                  <span>{(progressBarEgo * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-zinc-800">
                  <div
                    className="h-1.5 rounded-full bg-cyan-500 transition-all duration-100"
                    style={{ width: `${progressBarEgo * 100}%` }}
                  />
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-green-500/25 bg-zinc-950 p-4">
              <div className="mb-3 flex items-center justify-between">
                <span className="font-mono text-xs font-bold tracking-widest text-green-400">
                  CAR B — HUMAN
                </span>
              </div>
              <div className="mb-3">
                <div className="mb-1 font-mono text-xs text-zinc-500">LAPS</div>
                <div className="font-mono text-3xl font-black text-white">
                  {frame.lap_opp}
                </div>
              </div>
              <div>
                <div className="mb-1 flex justify-between font-mono text-xs text-zinc-500">
                  <span>PROGRESS</span>
                  <span>{(progressBarOpp * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-zinc-800">
                  <div
                    className="h-1.5 rounded-full bg-green-500 transition-all duration-100"
                    style={{ width: `${progressBarOpp * 100}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
