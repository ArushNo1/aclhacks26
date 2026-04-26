'use client';

import React, { useEffect, useRef, useState, CSSProperties } from 'react';
import {
  useTick, useFrameCounter,
  Label, BigNum, Dot, Divider,
  CameraFeed, SteeringGauge, ThrottleBar,
  RaceLights, TrackMap, LossChart,
  MQTTLog, DeviceHealth,
  C1, C2, CV, BG, SURFACE, SURFACE2, BORDER, BORDER2,
} from './shared';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ActTitle({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '0.18em',
      color,
      textTransform: 'uppercase' as const,
    }}>
      {label}
    </span>
  );
}

function card(extra: CSSProperties = {}): CSSProperties {
  return {
    background: SURFACE,
    border: `1px solid ${BORDER}`,
    borderRadius: 4,
    padding: 16,
    ...extra,
  };
}

function KV({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
      <Label>{label}</Label>
      <span style={{
        fontFamily: "var(--font-jetbrains-mono), 'JetBrains Mono', monospace",
        fontSize: 11,
        color: color ?? 'rgba(255,255,255,0.7)',
      }}>{value}</span>
    </div>
  );
}

// ─── ACT 1: CAPTURE ──────────────────────────────────────────────────────────

export function ActCapture() {
  const t = useTick(16);
  const frames = useFrameCounter(true);

  const steer = Math.sin(t * 0.72) * 0.58 + Math.sin(t * 1.37) * 0.18;
  const throttle = ((Math.sin(t * 0.51) + 1) / 2) * 0.55 + 0.22;
  const duration = Math.floor(t);
  const mm = String(Math.floor(duration / 60)).padStart(2, '0');
  const ss = String(duration % 60).padStart(2, '0');

  return (
    <div style={{
      flex: 1,
      display: 'grid',
      gridTemplateColumns: '1fr 270px',
      gap: 12,
      padding: 12,
      minHeight: 0,
      background: BG,
      overflow: 'hidden',
    }}>
      {/* Left: camera */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ActTitle label="ACT 1 · CAPTURE" color={C1} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Dot color="#22c55e" size={6} pulse />
            <Label style={{ color: '#22c55e' }}>TELEOP ACTIVE</Label>
          </div>
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <CameraFeed color={C1} label="CAR 1 · DEEPRACER" mode="manual" style={{ height: '100%' }} />
        </div>
      </div>

      {/* Right column */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, overflow: 'auto' }}>
        {/* Leap input */}
        <div style={card({ display: 'flex', flexDirection: 'column', gap: 10 })}>
          <Label>LEAP MOTION INPUT</Label>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
            <SteeringGauge value={steer} color={C1} />
            <ThrottleBar value={throttle} color={C1} />
          </div>
        </div>

        {/* Frames */}
        <div style={card({ display: 'flex', flexDirection: 'column', gap: 6 })}>
          <Label>FRAMES CAPTURED</Label>
          <BigNum value={frames.toLocaleString()} size={36} color={C1} />
          <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
            <div>
              <Label>DURATION</Label>
              <div style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: 13,
                color: 'rgba(255,255,255,0.6)',
              }}>{mm}:{ss}</div>
            </div>
            <div>
              <Label>DATASET</Label>
              <div style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: 13,
                color: 'rgba(255,255,255,0.6)',
              }}>{Math.floor(frames / 300 * 10) / 10} MB</div>
            </div>
          </div>
        </div>

        {/* Live signals */}
        <div style={card({ display: 'flex', flexDirection: 'column', gap: 8 })}>
          <Label>LIVE SIGNALS</Label>
          <Divider />
          <KV label="STEER" value={steer >= 0 ? `+${steer.toFixed(3)}` : steer.toFixed(3)} color={C1} />
          <KV label="THROTTLE" value={throttle.toFixed(3)} color={C1} />
          <KV label="FPS" value="30.0" />
          <KV label="POLICY" value="COLLECTING" color="#22c55e" />
        </div>

        {/* Status pill */}
        <div style={{
          ...card({ padding: '8px 12px' }),
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <Dot color="#eab308" size={7} pulse />
          <span style={{
            fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
            fontSize: 9,
            letterSpacing: '0.15em',
            color: '#eab308',
          }}>TRAINING · PENDING</span>
        </div>
      </div>
    </div>
  );
}

// ─── Loss generation ──────────────────────────────────────────────────────────

function generateLossPoints(): number[] {
  const pts: number[] = [];
  let l = 2.38;
  for (let i = 0; i < 200; i++) {
    l = l * (0.971 + Math.random() * 0.004) + (Math.random() - 0.5) * 0.028;
    l = Math.max(l, 0.048 + Math.random() * 0.01);
    pts.push(l);
  }
  return pts;
}

// ─── ACT 2: CLONE ────────────────────────────────────────────────────────────

export function ActClone({ car1Name, car2Name }: { car1Name: string; car2Name: string }) {
  const [elapsed, setElapsed] = useState(0);
  const [points] = useState<number[]>(() => generateLossPoints());
  const done = elapsed >= 200;
  const progress = Math.min(elapsed / 200, 1);
  const currentEpoch = Math.floor(elapsed);
  const currentLoss = done ? points[points.length - 1] : (points[currentEpoch] ?? 0);

  useEffect(() => {
    if (done) return;
    const id = setInterval(() => setElapsed(e => Math.min(e + 1, 200)), 80);
    return () => clearInterval(id);
  }, [done]);

  return (
    <div style={{
      flex: 1,
      display: 'grid',
      gridTemplateColumns: '300px 1fr 230px',
      gap: 12,
      padding: 12,
      minHeight: 0,
      background: BG,
      overflow: 'hidden',
    }}>
      {/* Left: camera + status */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
        <ActTitle label="ACT 2 · CLONE" color={CV} />
        <div style={{ flex: 1, minHeight: 0 }}>
          <CameraFeed color={CV} label="CAR 1 · TRAINING DATA" mode="manual" style={{ height: '100%' }} />
        </div>
        <div style={card({ padding: '10px 12px' })}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Dot color={done ? '#22c55e' : CV} size={7} pulse={!done} />
            <Label style={{ color: done ? '#22c55e' : CV }}>
              {done ? 'TRAINING COMPLETE' : 'BEHAVIORAL CLONING'}
            </Label>
          </div>
        </div>
      </div>

      {/* Center: loss chart + metrics */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0, overflow: 'auto' }}>
        <div style={card({ padding: 12 })}>
          <Label style={{ marginBottom: 8, display: 'block' }}>TRAINING LOSS</Label>
          <LossChart points={points} progress={progress} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {[
            { label: 'EPOCH', value: `${currentEpoch} / 200`, color: CV },
            { label: 'LOSS', value: currentLoss.toFixed(4), color: CV },
            { label: 'LR', value: '1e-4', color: 'rgba(255,255,255,0.6)' },
            { label: 'BATCH', value: '32', color: 'rgba(255,255,255,0.6)' },
          ].map(m => (
            <div key={m.label} style={card({ padding: '10px 14px' })}>
              <Label>{m.label}</Label>
              <div style={{
                fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
                fontSize: 18,
                fontWeight: 700,
                color: m.color,
                marginTop: 4,
                textShadow: `0 0 12px ${m.color}80`,
              }}>{m.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Right: policy badge + car 2 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Policy badge */}
        <div style={{
          ...card(),
          border: done ? `1px solid ${CV}44` : `1px solid ${BORDER}`,
          boxShadow: done ? `0 0 20px ${CV}22` : 'none',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          flex: 1,
        }}>
          <Label>POLICY</Label>
          <div style={{
            fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
            fontSize: 22,
            fontWeight: 900,
            color: done ? CV : 'rgba(255,255,255,0.15)',
            textShadow: done ? `0 0 20px ${CV}` : 'none',
            textAlign: 'center' as const,
            padding: '8px 0',
          }}>
            {done ? 'v1.0' : '- - -'}
          </div>
          {done && (
            <>
              <div style={{
                fontFamily: "var(--font-orbitron), monospace",
                fontSize: 10,
                color: CV,
                letterSpacing: '0.1em',
                textAlign: 'center' as const,
              }}>{car1Name} v1</div>
              <Divider />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  ['ARCH', 'CNN + MLP'],
                  ['INPUT', '640×480 RGB'],
                  ['OUTPUT', 'steer, throttle'],
                  ['LOSS', currentLoss.toFixed(4)],
                  ['PARAMS', '2.1M'],
                ].map(([k, v]) => (
                  <KV key={k} label={k} value={v} color={CV} />
                ))}
              </div>
            </>
          )}
        </div>

        {/* Car 2 */}
        <div style={card({ display: 'flex', flexDirection: 'column', gap: 8 })}>
          <Label>CAR 2 STATUS</Label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Dot color={C2} size={7} />
            <span style={{
              fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
              fontSize: 10,
              color: C2,
              letterSpacing: '0.1em',
            }}>{car2Name} v1</span>
          </div>
          <Label style={{ color: 'rgba(255,255,255,0.4)', fontSize: 9 }}>
            Pre-trained · Ready to race
          </Label>
        </div>
      </div>
    </div>
  );
}

// ─── ACT 3: RACE ─────────────────────────────────────────────────────────────

function fmtTime(s: number): string {
  return `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}`;
}

function lapDelta(times: number[]): string | null {
  if (times.length < 2) return null;
  return (times[times.length - 1] - times[times.length - 2]).toFixed(3);
}

function bestLap(times: number[]): number | null {
  if (times.length < 2) return null;
  let best = Infinity;
  for (let i = 1; i < times.length; i++) {
    const diff = times[i] - times[i - 1];
    if (diff < best) best = diff;
  }
  return best === Infinity ? null : best;
}

export function ActRace({ car1Name, car2Name }: { car1Name: string; car2Name: string }) {
  const t = useTick(16);
  const [lightPhase, setLightPhase] = useState<'off' | 'red' | 'yellow' | 'green'>('off');
  const [started, setStarted] = useState(false);
  const [raceClock, setRaceClock] = useState(0);
  const [car1Laps, setCar1Laps] = useState<number[]>([0]);
  const [car2Laps, setCar2Laps] = useState<number[]>([0]);
  const prevCar1T = useRef<number>(0);
  const prevCar2T = useRef<number>(0);

  const car1T = (t * 0.030) % 1;
  const car2T = (t * 0.027 + 0.48) % 1;

  // Light sequence on mount
  useEffect(() => {
    const t1 = setTimeout(() => setLightPhase('red'), 600);
    const t2 = setTimeout(() => setLightPhase('yellow'), 1600);
    const t3 = setTimeout(() => { setLightPhase('green'); setStarted(true); }, 2800);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, []);

  // Race clock
  useEffect(() => {
    if (!started) return;
    const id = setInterval(() => setRaceClock(c => +(c + 0.1).toFixed(1)), 100);
    return () => clearInterval(id);
  }, [started]);

  // Lap detection
  useEffect(() => {
    const prev1 = prevCar1T.current;
    if (prev1 > 0.88 && car1T < 0.12) {
      setCar1Laps(laps => [...laps, raceClock]);
    }
    prevCar1T.current = car1T;
  }, [car1T, raceClock]);

  useEffect(() => {
    const prev2 = prevCar2T.current;
    if (prev2 > 0.88 && car2T < 0.12) {
      setCar2Laps(laps => [...laps, raceClock]);
    }
    prevCar2T.current = car2T;
  }, [car2T, raceClock]);

  const car1LapCount = car1Laps.length - 1;
  const car2LapCount = car2Laps.length - 1;

  const leaderboard = [
    {
      name: car1Name,
      color: C1,
      laps: car1LapCount,
      lastLap: car1LapCount > 0 ? lapDelta(car1Laps) : null,
      best: bestLap(car1Laps),
    },
    {
      name: car2Name,
      color: C2,
      laps: car2LapCount,
      lastLap: car2LapCount > 0 ? lapDelta(car2Laps) : null,
      best: bestLap(car2Laps),
    },
  ].sort((a, b) => b.laps - a.laps);

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      padding: 12,
      minHeight: 0,
      background: BG,
      overflow: 'hidden',
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0 }}>
        <ActTitle label="ACT 3 · RACE" color={C2} />
        <Divider vertical style={{ height: 20 }} />
        <RaceLights phase={lightPhase} />
        <span style={{
          fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
          fontSize: 22,
          fontWeight: 700,
          color: started ? '#fff' : 'rgba(255,255,255,0.3)',
          letterSpacing: '0.05em',
          textShadow: started ? '0 0 20px rgba(255,255,255,0.3)' : 'none',
        }}>
          {fmtTime(raceClock)}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Dot color={started ? '#22c55e' : '#eab308'} size={7} pulse />
          <Label style={{ color: started ? '#22c55e' : '#eab308' }}>
            {started ? 'RACING' : 'STAGING'}
          </Label>
        </div>
      </div>

      {/* Camera feeds row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, height: 200, flexShrink: 0 }}>
        {[
          { name: car1Name, color: C1, lapCount: car1LapCount, mode: 'manual' as const },
          { name: car2Name, color: C2, lapCount: car2LapCount, mode: 'auto' as const },
        ].map(car => (
          <div key={car.name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', gap: 10 }}>
              <Label style={{ color: car.color }}>{car.name}</Label>
              <Label>LAP {car.lapCount}</Label>
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <CameraFeed color={car.color} label={car.name} mode={car.mode} style={{ height: '100%' }} />
            </div>
          </div>
        ))}
      </div>

      {/* Bottom row */}
      <div style={{ display: 'flex', gap: 10, flex: 1, minHeight: 0 }}>
        {/* Track map */}
        <div style={{ ...card(), width: 300, display: 'flex', flexDirection: 'column', gap: 8, flexShrink: 0 }}>
          <Label>TRACK MAP</Label>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <TrackMap car1T={car1T} car2T={car2T} />
          </div>
        </div>

        {/* Leaderboard */}
        <div style={{ ...card(), flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Label>LEADERBOARD</Label>
          <Divider />
          {leaderboard.map((entry, i) => (
            <div key={entry.name} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              padding: '10px 12px',
              background: SURFACE2,
              borderRadius: 4,
              border: `1px solid ${entry.color}22`,
            }}>
              <span style={{
                fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
                fontSize: 24,
                fontWeight: 900,
                color: i === 0 ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.3)',
                width: 28,
              }}>{i + 1}</span>
              <Dot color={entry.color} size={10} />
              <div style={{ flex: 1 }}>
                <div style={{
                  fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
                  fontSize: 13,
                  fontWeight: 700,
                  color: entry.color,
                }}>{entry.name}</div>
                <Label>POLICY v1</Label>
              </div>
              <div style={{ textAlign: 'right' as const }}>
                <div style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: 12,
                  color: 'rgba(255,255,255,0.7)',
                }}>LAPS: {entry.laps}</div>
                <div style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: 10,
                  color: 'rgba(255,255,255,0.35)',
                }}>
                  LAST: {entry.lastLap ? `${entry.lastLap}s` : '--'}
                </div>
                <div style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: 10,
                  color: '#22c55e',
                }}>
                  BEST: {entry.best ? `${entry.best.toFixed(3)}s` : '--'}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── ACT 4: DEBUG ────────────────────────────────────────────────────────────

export function ActDebug() {
  return (
    <div style={{
      flex: 1,
      display: 'grid',
      gridTemplateColumns: '1fr 380px',
      gap: 12,
      padding: 12,
      minHeight: 0,
      background: BG,
      overflow: 'hidden',
    }}>
      {/* Left: MQTT monitor */}
      <div style={{ ...card({ padding: 0 }), display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div style={{ padding: '10px 14px', borderBottom: `1px solid ${BORDER}`, flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ActTitle label="ACT 4 · DEBUG" color="rgba(255,255,255,0.4)" />
            <Divider vertical style={{ height: 14 }} />
            <Label>MQTT MONITOR</Label>
            <Dot color="#22c55e" size={6} pulse />
          </div>
        </div>
        <MQTTLog />
      </div>

      {/* Right: device health + network */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflow: 'auto' }}>
        <Label>DEVICE HEALTH</Label>
        <DeviceHealth />

        {/* Network panel */}
        <div style={card({ display: 'flex', flexDirection: 'column', gap: 10 })}>
          <Label>NETWORK</Label>
          <Divider />
          {[
            { label: 'SSID', value: 'GhostRacer-5G' },
            { label: 'ROUTER', value: '192.168.1.1' },
            { label: 'BROKER', value: '127.0.0.1:1883' },
            { label: 'LATENCY', value: '2.3ms' },
          ].map(({ label, value }) => (
            <KV key={label} label={label} value={value} />
          ))}
        </div>
      </div>
    </div>
  );
}
