'use client';

import React from 'react';
import {
  Label, Dot, Divider,
  CameraFeed, SteeringGauge, ThrottleBar,
  RaceLights,
  C1, C2, BG, SURFACE2,
} from '../shared';
import { api } from '../../../lib/api';
import { useRace, useHand, useStream, useTraining, useCapture } from '../../../lib/useStream';
import { ActButton, ActTitle, KV, card, fmtTime } from './common';

// ─── Layout constants ───────────────────────────────────────────────────────
const RIGHT_RAIL = 360;          // ghost-clone panel width (matches capture)
const TELEM_HEIGHT = 78;         // bottom stat strip height

export function ActRace({ car1Name, car2Name }: { car1Name: string; car2Name: string }) {
  const race = useRace();
  const hand = useHand();
  const training = useTraining();
  const capture = useCapture();
  const fps = useStream(s => s?.fps ?? 0);
  const polVer = useStream(s => s?.policy_version ?? null);

  const lightPhase = race?.light_phase ?? 'off';
  const started = race?.started ?? false;
  const raceClock = race?.race_clock ?? 0;
  const car1T = race?.car1.position_on_track ?? 0;
  const car2T = race?.car2.position_on_track ?? 0;
  const car1Lap = race?.car1.lap_count ?? 0;
  const car2Lap = race?.car2.lap_count ?? 0;
  const car1Best = race?.car1.best_lap_s ?? null;
  const car2Best = race?.car2.best_lap_s ?? null;
  const car1Last = race?.car1.last_lap_s ?? null;
  const car2Last = race?.car2.last_lap_s ?? null;

  const steer = hand?.steer ?? 0;
  const throttle = hand?.throttle ?? 0;

  const trainedFrames = capture?.frames ?? 0;
  const trainedEpochs = training?.total_epochs ?? 0;
  const finalLoss = training?.current_loss ?? (training?.loss_points?.length
    ? training.loss_points[training.loss_points.length - 1]
    : 0);

  const onStart = () => api.raceStart().catch(console.error);
  const onReset = () => api.raceReset().catch(console.error);

  const stateLabel = started ? 'RACING' : 'STAGING';
  const stateColor = started ? '#22c55e' : '#eab308';

  // Lap delta — positive means player ahead.
  const lapDelta = car1Lap - car2Lap;
  const gapLabel = lapDelta === 0 ? 'EVEN' : lapDelta > 0 ? `+${lapDelta} YOU` : `${lapDelta} CLONE`;
  const gapColor = lapDelta === 0 ? 'rgba(255,255,255,0.7)' : lapDelta > 0 ? C1 : C2;

  return (
    <div style={{
      flex: 1,
      display: 'grid',
      gridTemplateColumns: `1fr ${RIGHT_RAIL}px`,
      gap: 14,
      padding: 14,
      minHeight: 0,
      background: BG,
      overflow: 'hidden',
    }}>
      {/* ─── LEFT: race ────────────────────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateRows: `auto 1fr ${TELEM_HEIGHT}px`,
        gap: 12,
        minHeight: 0,
      }}>
        <Header
          stateLabel={stateLabel}
          stateColor={stateColor}
          lightPhase={lightPhase}
          raceClock={raceClock}
          raceStarted={started}
          onRaceStart={onStart}
          onRaceReset={onReset}
        />

        {/* Player POV fills the center; Clone POV is overlaid as a PIP in the top-left. */}
        <div style={{
          position: 'relative' as const,
          minHeight: 0,
          display: 'flex',
        }}>
          <div style={{ flex: 1, minWidth: 0, display: 'flex' }}>
            <PlayerPOV name={car1Name} lap={car1Lap} best={car1Best} last={car1Last} />
          </div>
          <ClonePiP name={car2Name} lap={car2Lap} best={car2Best} last={car2Last} polVer={polVer} />
        </div>

        <TelemetryStrip
          car1Name={car1Name}
          car2Name={car2Name}
          car1Lap={car1Lap}
          car2Lap={car2Lap}
          gapLabel={gapLabel}
          gapColor={gapColor}
          car1Best={car1Best}
          car2Best={car2Best}
          fps={fps}
          polVer={polVer}
        />
      </div>

      {/* ─── RIGHT: ghost-clone panel ─────────────────────────────────── */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        minHeight: 0,
        overflow: 'auto',
      }}>
        <CloneIdentityCard
          name={car2Name}
          polVer={polVer}
          frames={trainedFrames}
          epochs={trainedEpochs}
          loss={finalLoss}
        />

        <HandCam attached={hand?.attached ?? false} />

        <DriverInputCard
          steer={steer}
          throttle={throttle}
          name={car1Name}
        />

        <SpectatorMiniMap car1T={car1T} car2T={car2T} />
      </div>
    </div>
  );
}

// ─── Header ─────────────────────────────────────────────────────────────────
function Header({
  stateLabel, stateColor, lightPhase, raceClock, raceStarted,
  onRaceStart, onRaceReset,
}: {
  stateLabel: string;
  stateColor: string;
  lightPhase: 'off' | 'red' | 'yellow' | 'green';
  raceClock: number;
  raceStarted: boolean;
  onRaceStart: () => void;
  onRaceReset: () => void;
}) {
  return (
    <div style={{
      ...card({ padding: '10px 14px' }),
      display: 'flex',
      alignItems: 'center',
      gap: 14,
      flexWrap: 'wrap' as const,
      minHeight: 48,
    }}>
      <ActTitle label="ACT 3 · RACE" color={C2} />
      <Divider vertical style={{ height: 18 }} />
      <RaceLights phase={lightPhase} />
      <span style={{
        fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
        fontSize: 18,
        fontWeight: 700,
        color: raceStarted ? '#fff' : 'rgba(255,255,255,0.3)',
        letterSpacing: '0.05em',
      }}>
        {fmtTime(raceClock)}
      </span>
      <Divider vertical style={{ height: 18 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Dot color={stateColor} size={7} pulse />
        <Label style={{ color: stateColor }}>{stateLabel}</Label>
      </div>
      <Divider vertical style={{ height: 18 }} />
      {/* Make the matchup unmissable in the header itself */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.18em',
      }}>
        <span style={{ color: C1, textShadow: `0 0 8px ${C1}80` }}>YOU</span>
        <span style={{ color: 'rgba(255,255,255,0.35)' }}>VS</span>
        <span style={{ color: C2, textShadow: `0 0 8px ${C2}80` }}>YOUR CLONE</span>
      </div>

      <div style={{ flex: 1 }} />

      <div style={{ display: 'flex', gap: 8 }}>
        <ActButton onClick={onRaceStart} color="#22c55e" kind="solid">START RACE</ActButton>
        <ActButton onClick={onRaceReset} color="rgba(255,255,255,0.5)">RESET</ActButton>
      </div>
    </div>
  );
}

// ─── Player POV ─────────────────────────────────────────────────────────────
function PlayerPOV({
  name, lap, best, last,
}: {
  name: string;
  lap: number;
  best: number | null;
  last: number | null;
}) {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      minHeight: 0,
      minWidth: 0,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '0 4px',
      }}>
        <span style={{
          fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.2em',
          color: C1,
          textShadow: `0 0 8px ${C1}80`,
        }}>YOU</span>
        <Label style={{ color: 'rgba(255,255,255,0.5)' }}>{name}</Label>
        <Label>LAP {lap}</Label>
        <div style={{ flex: 1 }} />
        <Label style={{ color: 'rgba(255,255,255,0.4)' }}>
          LAST {last !== null ? `${last.toFixed(2)}s` : '--'}
        </Label>
        <Label style={{ color: '#22c55e' }}>
          BEST {best !== null ? `${best.toFixed(2)}s` : '--'}
        </Label>
      </div>
      <div style={{
        flex: 1,
        minHeight: 0,
        borderRadius: 6,
        overflow: 'hidden',
        border: `1px solid ${C1}33`,
        boxShadow: `0 0 24px ${C1}22`,
      }}>
        <CameraFeed
          color={C1}
          label={`${name} · YOUR POV`}
          src="/stream/player.mjpg"
          resolution="320×240"
          style={{ height: '100%' }}
        />
      </div>
    </div>
  );
}

// ─── Clone PIP — picture-in-picture overlay anchored to the top-right ──────
function ClonePiP({
  name, lap, best, last, polVer,
}: {
  name: string;
  lap: number;
  best: number | null;
  last: number | null;
  polVer: string | null;
}) {
  return (
    <div style={{
      position: 'absolute',
      top: 32,
      right: 12,
      width: 'min(28%, 320px)',
      aspectRatio: '4 / 3',
      borderRadius: 6,
      overflow: 'hidden',
      border: `1px solid ${C2}66`,
      boxShadow: `0 0 24px ${C2}33, 0 6px 24px rgba(0,0,0,0.55)`,
      background: BG,
      zIndex: 5,
    }}>
      <CameraFeed
        color={C2}
        label={`${name} · CLONE POV`}
        src="/stream/ai.mjpg"
        resolution="160×120"
        style={{ height: '100%' }}
      />
      {/* Top strip: YOUR CLONE label + lap/best */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0,
        padding: '5px 8px',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.75), transparent)',
        pointerEvents: 'none' as const,
      }}>
        <span style={{
          fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: '0.2em',
          color: C2,
          textShadow: `0 0 8px ${C2}80`,
        }}>YOUR CLONE</span>
        <Label style={{ fontSize: 8, color: 'rgba(255,255,255,0.5)' }}>{name}</Label>
        <div style={{ flex: 1 }} />
        <Label style={{ fontSize: 8 }}>LAP {lap}</Label>
        {best !== null && (
          <Label style={{ fontSize: 8, color: '#22c55e' }}>BEST {best.toFixed(2)}s</Label>
        )}
      </div>
      {/* Bottom strip: trained-on-you watermark */}
      <div style={{
        position: 'absolute',
        bottom: 0, left: 0, right: 0,
        padding: '5px 8px',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        background: 'linear-gradient(to top, rgba(0,0,0,0.75), transparent)',
        pointerEvents: 'none' as const,
      }}>
        <Dot color={C2} size={5} pulse />
        <span style={{
          fontFamily: "var(--font-jetbrains-mono), monospace",
          fontSize: 8,
          letterSpacing: '0.18em',
          color: C2,
          textTransform: 'uppercase' as const,
        }}>
          TRAINED ON YOU · {polVer ?? 'v1'}
        </span>
        <div style={{ flex: 1 }} />
        {last !== null && (
          <Label style={{ fontSize: 8, color: 'rgba(255,255,255,0.55)' }}>
            LAST {last.toFixed(2)}s
          </Label>
        )}
      </div>
    </div>
  );
}

// ─── Telemetry strip ───────────────────────────────────────────────────────
function TelemetryStrip({
  car1Name, car2Name,
  car1Lap, car2Lap,
  gapLabel, gapColor,
  car1Best, car2Best,
  fps, polVer,
}: {
  car1Name: string;
  car2Name: string;
  car1Lap: number;
  car2Lap: number;
  gapLabel: string;
  gapColor: string;
  car1Best: number | null;
  car2Best: number | null;
  fps: number;
  polVer: string | null;
}) {
  const cells = [
    { label: `${car1Name} LAP`, value: `${car1Lap}`, color: C1 },
    { label: `${car2Name} LAP`, value: `${car2Lap}`, color: C2 },
    { label: 'GAP', value: gapLabel, color: gapColor },
    { label: 'YOU · BEST', value: car1Best !== null ? `${car1Best.toFixed(2)}s` : '--', color: 'rgba(255,255,255,0.7)' },
    { label: 'CLONE · BEST', value: car2Best !== null ? `${car2Best.toFixed(2)}s` : '--', color: 'rgba(255,255,255,0.7)' },
    { label: 'FPS', value: fps.toFixed(1), color: 'rgba(255,255,255,0.7)' },
    { label: 'POLICY', value: polVer ?? '--', color: C2 },
  ];
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${cells.length}, 1fr)`,
      gap: 10,
    }}>
      {cells.map(c => (
        <div key={c.label} style={card({ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 4 })}>
          <Label>{c.label}</Label>
          <div style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: 14,
            color: c.color,
          }}>{c.value}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Right rail: Clone identity card ───────────────────────────────────────
function CloneIdentityCard({
  name, polVer, frames, epochs, loss,
}: {
  name: string;
  polVer: string | null;
  frames: number;
  epochs: number;
  loss: number;
}) {
  return (
    <div style={{
      ...card({ padding: 14 }),
      border: `1px solid ${C2}55`,
      boxShadow: `0 0 28px ${C2}22, inset 0 0 24px ${C2}11`,
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Dot color={C2} size={7} pulse />
        <Label style={{ color: C2 }}>OPPONENT · GHOST CLONE</Label>
      </div>
      <div style={{
        fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
        fontSize: 18,
        fontWeight: 900,
        color: C2,
        letterSpacing: '0.05em',
        textShadow: `0 0 14px ${C2}80`,
      }}>
        {name}
      </div>
      <div style={{
        fontFamily: "var(--font-jetbrains-mono), monospace",
        fontSize: 11,
        color: 'rgba(255,255,255,0.7)',
        lineHeight: 1.5,
      }}>
        A behaviour-cloned policy fitted on{' '}
        <span style={{ color: '#fff', fontWeight: 600 }}>your</span> driving.
        It sees the same camera you do and predicts steering and throttle
        from your demonstrations.
      </div>
      <Divider />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <KV label="POLICY" value={polVer ?? '--'} color={C2} />
        <KV label="TRAINED ON" value={frames > 0 ? `${frames.toLocaleString()} of YOUR frames` : '— frames'} />
        <KV label="EPOCHS" value={epochs > 0 ? `${epochs}` : '--'} />
        <KV label="FINAL LOSS" value={loss > 0 ? loss.toFixed(4) : '--'} />
        <KV label="ARCH" value="CNN + MLP" />
      </div>
    </div>
  );
}

// ─── Right rail: HandCam ────────────────────────────────────────────────────
function HandCam({ attached }: { attached: boolean }) {
  return (
    <div style={{
      width: '100%',
      aspectRatio: '4 / 3',
      flexShrink: 0,
    }}>
      {attached ? (
        <CameraFeed
          color={C1}
          label="YOUR HAND · LIVE"
          src="/stream/hand.mjpg"
          resolution="webcam"
          style={{ height: '100%' }}
        />
      ) : (
        <div style={card({
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center' as const,
        })}>
          <Label style={{ color: 'rgba(255,255,255,0.4)' }}>WEBCAM UNAVAILABLE</Label>
          <div style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: 11,
            color: 'rgba(255,255,255,0.5)',
            lineHeight: 1.55,
            padding: '0 14px',
          }}>
            Plug in a webcam, then restart{' '}
            <code style={{ background: SURFACE2, padding: '1px 4px', borderRadius: 2 }}>uvicorn</code>
            .
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Right rail: DriverInputCard (the human's live tank input) ─────────────
function DriverInputCard({ steer, throttle, name }: { steer: number; throttle: number; name: string }) {
  return (
    <div style={card({ display: 'flex', flexDirection: 'column', gap: 12 })}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Dot color={C1} size={7} pulse />
        <Label style={{ color: C1 }}>YOUR INPUT · {name}</Label>
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
      }}>
        <SteeringGauge value={steer} color={C1} />
        <ThrottleBar value={throttle} color={C1} />
      </div>
    </div>
  );
}

// ─── Right rail: Spectator bird's-eye camera ───────────────────────────────
function SpectatorMiniMap({ car1T: _car1T, car2T: _car2T }: { car1T: number; car2T: number }) {
  return (
    <div style={{
      ...card({
        padding: 0,
        overflow: 'hidden',
        position: 'relative' as const,
      }),
      aspectRatio: '1 / 1',
    }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/stream/spectator.mjpg"
        alt="top-down spectator"
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          background: '#0a0e1a',
          display: 'block',
        }}
      />
      <div style={{
        position: 'absolute',
        top: 8,
        left: 10,
        padding: '2px 6px',
        background: 'rgba(0,0,0,0.55)',
        borderRadius: 3,
      }}>
        <Label>SPECTATOR · TOP-DOWN</Label>
      </div>
    </div>
  );
}
