"use client";

import { useEffect, useState } from "react";
import { CameraIcon, HandIcon } from "./icons";

const RACE_STATES = ["IDLE", "TRAINING", "LIVE"] as const;
type RaceState = (typeof RACE_STATES)[number];

const stateMeta: Record<
  RaceState,
  { label: string; dot: string; text: string; ring: string }
> = {
  IDLE: {
    label: "Standby",
    dot: "bg-[var(--color-text-subtle)]",
    text: "text-[var(--color-text-muted)]",
    ring: "border-[var(--color-border)]",
  },
  TRAINING: {
    label: "Training",
    dot: "bg-[var(--color-warning)]",
    text: "text-[var(--color-warning)]",
    ring: "border-[var(--color-warning)]/40",
  },
  LIVE: {
    label: "Live race",
    dot: "bg-[var(--color-accent-soft)]",
    text: "text-[var(--color-accent-soft)]",
    ring: "border-[var(--color-accent)]/50",
  },
};

const cars = [
  {
    id: "A",
    policy: "human_a · v1",
    laps: 3,
    totalLaps: 5,
    bestLap: "00:42.3",
    accent: "var(--color-accent-soft)",
  },
  {
    id: "B",
    policy: "human_b · v1",
    laps: 2,
    totalLaps: 5,
    bestLap: "00:47.8",
    accent: "var(--color-text)",
  },
];

const leaderboard = [
  { rank: 1, policy: "human_a · v1", laps: 3, bestLap: "00:42.3" },
  { rank: 2, policy: "human_b · v1", laps: 2, bestLap: "00:47.8" },
  { rank: 3, policy: "baseline · v0", laps: 2, bestLap: "00:51.4" },
];

export default function LiveDashboard() {
  const [stateIdx, setStateIdx] = useState(2);
  const raceState = RACE_STATES[stateIdx];
  const meta = stateMeta[raceState];

  useEffect(() => {
    const id = setInterval(() => {
      setStateIdx((i) => (i + 1) % RACE_STATES.length);
    }, 12000);
    return () => clearInterval(id);
  }, []);

  return (
    <section
      id="race"
      className="border-t border-[var(--color-border)] bg-[var(--color-bg)] px-5 py-24"
    >
      <div className="mx-auto max-w-6xl">
        <header className="mb-12 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <span className="label">Race status</span>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">
              Status &amp; leaderboard
            </h2>
          </div>
          <div
            className={`inline-flex items-center gap-2.5 self-start rounded-full border px-4 py-2 ${meta.ring}`}
          >
            <span
              aria-hidden
              className={`block h-2 w-2 rounded-full ${meta.dot}`}
            />
            <span className={`text-sm font-semibold ${meta.text}`}>
              {meta.label}
            </span>
          </div>
        </header>

        <div className="mb-8 grid grid-cols-1 gap-5 md:grid-cols-2">
          {cars.map((car) => (
            <CarCard key={car.id} car={car} />
          ))}
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.4fr_1fr]">
          <Leaderboard />
          <HandCam />
        </div>
      </div>
    </section>
  );
}

function CarCard({
  car,
}: {
  car: { id: string; policy: string; laps: number; totalLaps: number; bestLap: string; accent: string };
}) {
  const pct = Math.round((car.laps / car.totalLaps) * 100);
  return (
    <article className="card p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className="flex h-8 w-8 items-center justify-center rounded-md font-mono text-sm font-bold"
            style={{
              background: `color-mix(in srgb, ${car.accent} 14%, transparent)`,
              color: car.accent,
            }}
          >
            {car.id}
          </span>
          <span className="text-sm text-[var(--color-text-muted)]">
            {car.policy}
          </span>
        </div>
        <span className="badge">Car {car.id}</span>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-6">
        <Metric label="Laps" value={`${car.laps}/${car.totalLaps}`} />
        <Metric label="Best lap" value={car.bestLap} accent={car.accent} />
      </div>

      <div className="mt-6">
        <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.12em] text-[var(--color-text-subtle)]">
          <span>Progress</span>
          <span>{pct}%</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--color-surface-2)]">
          <div
            className="h-full rounded-full transition-[width] duration-500"
            style={{ width: `${pct}%`, background: car.accent }}
          />
        </div>
      </div>
    </article>
  );
}

function Metric({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.12em] text-[var(--color-text-subtle)]">
        {label}
      </div>
      <div
        className="mt-1 font-mono text-3xl font-bold"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
    </div>
  );
}

function Leaderboard() {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">
          Leaderboard
        </h3>
        <span className="text-[11px] uppercase tracking-[0.12em] text-[var(--color-text-subtle)]">
          Today
        </span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-y border-[var(--color-border)] bg-[var(--color-surface-2)]/40 text-left text-[11px] uppercase tracking-[0.12em] text-[var(--color-text-subtle)]">
            <th className="px-5 py-2.5 font-semibold">Rank</th>
            <th className="px-5 py-2.5 font-semibold">Policy</th>
            <th className="px-5 py-2.5 font-semibold">Laps</th>
            <th className="px-5 py-2.5 text-right font-semibold">Best lap</th>
          </tr>
        </thead>
        <tbody>
          {leaderboard.map((row, i) => (
            <tr
              key={row.rank}
              className={
                i % 2 === 1 ? "bg-[var(--color-surface-2)]/30" : undefined
              }
            >
              <td className="px-5 py-3.5">
                <span
                  className={
                    row.rank === 1
                      ? "inline-flex h-6 min-w-6 items-center justify-center rounded-md bg-[var(--color-accent)]/15 px-1.5 font-mono text-xs font-bold text-[var(--color-accent-soft)]"
                      : "inline-flex h-6 min-w-6 items-center justify-center rounded-md bg-[var(--color-surface-2)] px-1.5 font-mono text-xs font-bold text-[var(--color-text-muted)]"
                  }
                >
                  #{row.rank}
                </span>
              </td>
              <td className="px-5 py-3.5 font-mono text-[var(--color-text)]">
                {row.policy}
              </td>
              <td className="px-5 py-3.5 text-[var(--color-text-muted)]">
                {row.laps}
              </td>
              <td className="px-5 py-3.5 text-right font-mono text-[var(--color-text)]">
                {row.bestLap}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HandCam() {
  return (
    <div className="card flex flex-col p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">
          Hand cam
        </h3>
        <span className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-[0.12em] text-[var(--color-text-subtle)]">
          <CameraIcon className="h-3 w-3" />
          Source
        </span>
      </div>
      <div className="mt-4 flex flex-1 items-center justify-center rounded-md border border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface-2)]/40 p-8">
        <div className="flex flex-col items-center text-center">
          <HandIcon className="h-10 w-10 text-[var(--color-text-subtle)]" />
          <div className="mt-3 text-sm text-[var(--color-text-muted)]">
            Waiting for hand input
          </div>
          <div className="mt-1 text-xs text-[var(--color-text-subtle)]">
            Connect a Leap Motion or webcam to begin.
          </div>
        </div>
      </div>
    </div>
  );
}
