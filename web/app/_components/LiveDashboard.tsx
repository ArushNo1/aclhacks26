"use client";

import { useState, useEffect } from "react";

const RACE_STATES = ["IDLE", "TRAINING", "LIVE"] as const;
type RaceState = (typeof RACE_STATES)[number];

const stateMeta: Record<RaceState, { color: string; bg: string; border: string }> = {
  IDLE: {
    color: "text-zinc-500",
    bg: "bg-zinc-950",
    border: "border-zinc-800",
  },
  TRAINING: {
    color: "text-yellow-400",
    bg: "bg-yellow-500/5",
    border: "border-yellow-500/30",
  },
  LIVE: {
    color: "text-green-400",
    bg: "bg-green-500/5",
    border: "border-green-500/30",
  },
};

const leaderboard = [
  { rank: 1, policy: "HUMAN_A v1", laps: 3, bestTime: "00:42.3", color: "text-cyan-400" },
  { rank: 2, policy: "HUMAN_B v1", laps: 2, bestTime: "00:47.8", color: "text-green-400" },
];

export default function LiveDashboard() {
  const [stateIdx, setStateIdx] = useState(0);
  const raceState = RACE_STATES[stateIdx];
  const meta = stateMeta[raceState];

  useEffect(() => {
    const id = setInterval(() => {
      setStateIdx((i) => (i + 1) % RACE_STATES.length);
    }, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="border-t border-zinc-900 bg-black px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <h2 className="mb-4 text-center font-mono text-sm font-bold tracking-widest text-cyan-500">
          LIVE RACE DASHBOARD
        </h2>

        <div
          className={`mx-auto mb-12 max-w-xs rounded-lg border px-6 py-3 text-center transition-all duration-700 ${meta.border} ${meta.bg}`}
        >
          <span className={`font-mono text-sm font-bold tracking-widest ${meta.color}`}>
            {raceState === "LIVE" && <span className="mr-2 animate-pulse">●</span>}
            {raceState}
          </span>
        </div>

        <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-cyan-500/20 bg-zinc-950 p-6">
            <div className="mb-5 flex items-center justify-between">
              <span className="font-mono text-xs font-bold tracking-widest text-cyan-400">
                CAR A
              </span>
              <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-0.5 font-mono text-xs text-cyan-300">
                Policy: HUMAN_A v1
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="mb-1 font-mono text-xs text-zinc-600">LAPS</div>
                <div className="font-mono text-4xl font-black text-white">3</div>
              </div>
              <div>
                <div className="mb-1 font-mono text-xs text-zinc-600">BEST LAP</div>
                <div className="font-mono text-4xl font-black text-cyan-400">42.3s</div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-green-500/20 bg-zinc-950 p-6">
            <div className="mb-5 flex items-center justify-between">
              <span className="font-mono text-xs font-bold tracking-widest text-green-400">
                CAR B
              </span>
              <span className="rounded-full border border-green-500/20 bg-green-500/10 px-3 py-0.5 font-mono text-xs text-green-300">
                Policy: HUMAN_B v1
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="mb-1 font-mono text-xs text-zinc-600">LAPS</div>
                <div className="font-mono text-4xl font-black text-white">2</div>
              </div>
              <div>
                <div className="mb-1 font-mono text-xs text-zinc-600">BEST LAP</div>
                <div className="font-mono text-4xl font-black text-green-400">47.8s</div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
            <h3 className="mb-4 font-mono text-xs font-bold tracking-widest text-zinc-500">
              LEADERBOARD
            </h3>
            <table className="w-full font-mono text-sm">
              <thead>
                <tr className="text-left">
                  <th className="pb-3 font-mono text-xs font-normal text-zinc-600">RANK</th>
                  <th className="pb-3 font-mono text-xs font-normal text-zinc-600">POLICY</th>
                  <th className="pb-3 font-mono text-xs font-normal text-zinc-600">LAPS</th>
                  <th className="pb-3 text-right font-mono text-xs font-normal text-zinc-600">
                    BEST
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {leaderboard.map((row) => (
                  <tr key={row.rank}>
                    <td className="py-3 text-zinc-500">#{row.rank}</td>
                    <td className={`py-3 ${row.color}`}>{row.policy}</td>
                    <td className="py-3 text-white">{row.laps}</td>
                    <td className={`py-3 text-right ${row.color}`}>{row.bestTime}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="hand-cam-card rounded-lg border border-zinc-800 bg-zinc-950 p-6">
            <h3 className="mb-4 font-mono text-xs font-bold tracking-widest text-zinc-500">
              HAND CAM FEED
            </h3>
            <div className="flex h-40 items-center justify-center rounded border border-dashed border-zinc-700">
              <div className="text-center">
                <div className="mb-2 text-4xl">✋</div>
                <div className="font-mono text-xs text-zinc-600">AWAITING FEED</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
