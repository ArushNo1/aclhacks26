"use client";

import { useState, useEffect } from "react";

const RACE_STATES = ["IDLE", "TRAINING", "LIVE"] as const;
type RaceState = (typeof RACE_STATES)[number];

const dotColor: Record<RaceState, string> = {
  IDLE: "text-zinc-600",
  TRAINING: "text-yellow-400",
  LIVE: "text-green-400",
};

const dotPulse: Record<RaceState, boolean> = {
  IDLE: false,
  TRAINING: true,
  LIVE: true,
};

const statusStyle: Record<RaceState, React.CSSProperties> = {
  IDLE: { borderColor: "rgba(63,63,70,0.8)", backgroundColor: "transparent" },
  TRAINING: { borderColor: "rgba(234,179,8,0.3)", backgroundColor: "rgba(234,179,8,0.04)" },
  LIVE: { borderColor: "rgba(34,197,94,0.35)", backgroundColor: "rgba(34,197,94,0.05)" },
};

const leaderboard = [
  { rank: 1, policy: "HUMAN_A v1", laps: "--", bestTime: "--:--.--", color: "text-cyan-400" },
  { rank: 2, policy: "HUMAN_B v1", laps: "--", bestTime: "--:--.--", color: "text-green-400" },
];

export default function LiveDashboard() {
  const [stateIdx, setStateIdx] = useState(0);
  const raceState = RACE_STATES[stateIdx];

  useEffect(() => {
    const id = setInterval(() => {
      setStateIdx((i) => (i + 1) % RACE_STATES.length);
    }, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <section id="dashboard" className="border-t border-zinc-800 bg-black px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <h2 className="mb-10 text-center font-mono text-sm font-bold tracking-widest text-cyan-500">
          LIVE RACE DASHBOARD
        </h2>

        <div
          className="mx-auto mb-12 max-w-xs rounded-lg border px-6 py-3 text-center transition-colors duration-700"
          style={statusStyle[raceState]}
        >
          <span className={`inline-flex items-center gap-2 font-mono text-sm font-bold tracking-widest ${dotColor[raceState]}`}>
            <span className={dotPulse[raceState] ? "animate-pulse" : ""}>●</span>
            {raceState}
          </span>
        </div>

        <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-cyan-500/25 bg-zinc-950 p-6">
            <div className="mb-5 flex items-center justify-between">
              <span className="font-mono text-xs font-bold tracking-widest text-cyan-400">
                CAR A
              </span>
              <span className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-0.5 font-mono text-xs text-cyan-300">
                Policy: HUMAN_A v1
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="mb-1 font-mono text-xs text-zinc-500">LAPS</div>
                <div className="font-mono text-4xl font-black text-white">--</div>
              </div>
              <div>
                <div className="mb-1 font-mono text-xs text-zinc-500">BEST LAP</div>
                <div className="font-mono text-2xl font-black text-cyan-400">--:--.--</div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-green-500/25 bg-zinc-950 p-6">
            <div className="mb-5 flex items-center justify-between">
              <span className="font-mono text-xs font-bold tracking-widest text-green-400">
                CAR B
              </span>
              <span className="rounded-full border border-green-500/25 bg-green-500/10 px-3 py-0.5 font-mono text-xs text-green-300">
                Policy: HUMAN_B v1
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="mb-1 font-mono text-xs text-zinc-500">LAPS</div>
                <div className="font-mono text-4xl font-black text-white">--</div>
              </div>
              <div>
                <div className="mb-1 font-mono text-xs text-zinc-500">BEST LAP</div>
                <div className="font-mono text-2xl font-black text-green-400">--:--.--</div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
            <h3 className="mb-4 font-mono text-xs font-bold tracking-widest text-zinc-400">
              LEADERBOARD
            </h3>
            <table className="w-full font-mono text-sm">
              <thead>
                <tr className="text-left">
                  <th className="pb-3 font-mono text-xs font-normal text-zinc-600">RANK</th>
                  <th className="pb-3 font-mono text-xs font-normal text-zinc-600">POLICY</th>
                  <th className="pb-3 font-mono text-xs font-normal text-zinc-600">LAPS</th>
                  <th className="pb-3 text-right font-mono text-xs font-normal text-zinc-600">BEST</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {leaderboard.map((row) => (
                  <tr key={row.rank}>
                    <td className="py-3 text-zinc-500">#{row.rank}</td>
                    <td className={`py-3 ${row.color}`}>{row.policy}</td>
                    <td className="py-3 text-zinc-400">{row.laps}</td>
                    <td className={`py-3 text-right ${row.color}`}>{row.bestTime}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
            <h3 className="mb-4 font-mono text-xs font-bold tracking-widest text-zinc-400">
              HAND CAM FEED
            </h3>
            <div className="hand-cam-inner flex h-40 items-center justify-center rounded border border-dashed border-zinc-700">
              <div className="text-center">
                <div className="mb-2 text-4xl">✋</div>
                <div className="font-mono text-xs text-zinc-500">AWAITING FEED</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
