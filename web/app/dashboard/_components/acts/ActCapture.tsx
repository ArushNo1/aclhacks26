'use client';

import React from 'react';
import {
  Label, Dot, Divider,
  CameraFeed, SteeringGauge, ThrottleBar,
  RaceLights,
  C1, BG, SURFACE2,
} from '../shared';
import { api } from '../../../lib/api';
import { useRace, useCapture, useHand, useStream } from '../../../lib/useStream';
import { ActButton, ActTitle, KV, card, fmtTime } from './common';
import { CalibrationCard } from './CalibrationCard';

// ─── Layout constants ───────────────────────────────────────────────────────
const RIGHT_RAIL = 360;          // hand panel width
const TELEM_HEIGHT = 78;         // bottom stat strip height

export function ActCapture() {
  const cap = useCapture();
  const hand = useHand();
  const race = useRace();
  const fps = useStream(s => s?.fps ?? 0);

  const recording = cap?.recording ?? false;
  const frames = cap?.frames ?? 0;
  const duration = Math.floor(cap?.duration_s ?? 0);
  const mm = String(Math.floor(duration / 60)).padStart(2, '0');
  const ss = String(duration % 60).padStart(2, '0');
  const datasetMb = (frames * 160 * 120 * 3) / (1024 * 1024);

  const steer = hand?.steer ?? 0;
  const throttle = hand?.throttle ?? 0;
  const handAttached = hand?.attached ?? false;
  const handCalibrated = hand?.calibrated ?? false;
  const calibration = hand?.calibration;

  const lightPhase = race?.light_phase ?? 'off';
  const raceClock = race?.race_clock ?? 0;
  const car1Lap = race?.car1.lap_count ?? 0;
  const car2Lap = race?.car2.lap_count ?? 0;
  const raceStarted = race?.started ?? false;

  const onCapStart = () => api.captureStart().catch(console.error);
  const onCapStop = () => api.captureStop().then(r => r.path && console.log('[capture] saved', r.path)).catch(console.error);
  const onRaceStart = () => api.raceStart().catch(console.error);
  const onRaceReset = () => api.raceReset().catch(console.error);
  const calStart = () => api.handCalibrateStart().catch(console.error);
  const calCapture = () => api.handCalibrateCapture().catch(console.error);
  const calRedo = () => api.handCalibrateRedo().catch(console.error);
  const calCancel = () => api.handCalibrateCancel().catch(console.error);
  const calReset = () => api.handReset().catch(console.error);

  const stateLabel =
    recording ? 'RECORDING'
    : !handAttached ? 'NO WEBCAM'
    : !handCalibrated ? 'NEEDS CALIBRATION'
    : raceStarted ? 'DRIVING' : 'READY';
  const stateColor =
    recording ? '#22c55e'
    : !handAttached ? 'rgba(255,255,255,0.4)'
    : !handCalibrated ? '#eab308'
    : C1;

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
      {/* ─── LEFT: game ───────────────────────────────────────────────── */}
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
          raceStarted={raceStarted}
          recording={recording}
          handReady={handAttached && handCalibrated}
          onRaceStart={onRaceStart}
          onRaceReset={onRaceReset}
          onCapStart={onCapStart}
          onCapStop={onCapStop}
        />

        {/* Player POV + spectator, split 50/50 across the row */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 12,
          minHeight: 0,
        }}>
          <PlayerPOV car1Lap={car1Lap} car2Lap={car2Lap} />
          <Spectator />
        </div>

        <TelemetryStrip
          frames={frames}
          duration={`${mm}:${ss}`}
          datasetMb={datasetMb}
          fps={fps}
          hasLeft={hand?.has_left ?? false}
          hasRight={hand?.has_right ?? false}
          recording={recording}
        />
      </div>

      {/* ─── RIGHT: hand panel ────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        minHeight: 0,
        overflow: 'auto',
      }}>
        <HandCam attached={handAttached} />

        <CalibrationCard
          attached={handAttached}
          calibrated={handCalibrated}
          calibration={calibration}
          profile={hand?.profile ?? null}
          onStart={calStart}
          onCapture={calCapture}
          onRedo={calRedo}
          onCancel={calCancel}
          onReset={calReset}
        />

        <TankInputCard steer={steer} throttle={throttle} />

        {cap?.last_save_path && <LastSaveCard path={cap.last_save_path} />}
      </div>
    </div>
  );
}

// ─── Header ─────────────────────────────────────────────────────────────────
function Header({
  stateLabel, stateColor, lightPhase, raceClock, raceStarted,
  recording, handReady,
  onRaceStart, onRaceReset, onCapStart, onCapStop,
}: {
  stateLabel: string;
  stateColor: string;
  lightPhase: 'off' | 'red' | 'yellow' | 'green';
  raceClock: number;
  raceStarted: boolean;
  recording: boolean;
  handReady: boolean;
  onRaceStart: () => void;
  onRaceReset: () => void;
  onCapStart: () => void;
  onCapStop: () => void;
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
      <ActTitle label="ACT 1 · CAPTURE" color={C1} />
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
        <Dot color={stateColor} size={7} pulse={recording} />
        <Label style={{ color: stateColor }}>{stateLabel}</Label>
      </div>

      <div style={{ flex: 1 }} />

      <div style={{ display: 'flex', gap: 8 }}>
        <ActButton onClick={onRaceStart} color="#22c55e">START RACE</ActButton>
        <ActButton onClick={onRaceReset} color="rgba(255,255,255,0.5)">RESET</ActButton>
      </div>
      {handReady && (
        recording
          ? <ActButton onClick={onCapStop} color="#f43f5e" kind="solid">STOP REC</ActButton>
          : <ActButton onClick={onCapStart} color="#22c55e" kind="solid">REC</ActButton>
      )}
    </div>
  );
}

// ─── Player POV ─────────────────────────────────────────────────────────────
function PlayerPOV({ car1Lap, car2Lap }: { car1Lap: number; car2Lap: number }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      minHeight: 0,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '0 4px',
      }}>
        <Label style={{ color: C1 }}>YOUR POV</Label>
        <Label style={{ color: 'rgba(255,255,255,0.5)' }}>LAP {car1Lap}</Label>
        <div style={{ flex: 1 }} />
        <Label>AI LAP {car2Lap}</Label>
      </div>
      <div style={{
        flex: 1,
        minHeight: 0,
        borderRadius: 6,
        overflow: 'hidden',
      }}>
        <CameraFeed
          color={C1}
          label="PLAYER · CAR 1"
          src="/stream/player.mjpg"
          resolution="320×240"
          style={{ height: '100%' }}
        />
      </div>
    </div>
  );
}

// ─── Spectator (square, full top-down render with no clipping) ─────────────
function Spectator() {
  return (
    <div style={{
      ...card({
        padding: 0,
        overflow: 'hidden',
        position: 'relative' as const,
      }),
      // Grid cell stretches us to fill its 50% column. The image inside
      // uses objectFit:contain so the full 600x600 render stays visible
      // (with horizontal letterboxing on wide cells).
      minHeight: 0,
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

// ─── Telemetry strip ───────────────────────────────────────────────────────
function TelemetryStrip({
  frames, duration, datasetMb, fps, hasLeft, hasRight, recording,
}: {
  frames: number;
  duration: string;
  datasetMb: number;
  fps: number;
  hasLeft: boolean;
  hasRight: boolean;
  recording: boolean;
}) {
  const cells = [
    { label: 'FRAMES', value: frames.toLocaleString(), color: recording ? C1 : 'rgba(255,255,255,0.7)' },
    { label: 'DURATION', value: duration, color: 'rgba(255,255,255,0.7)' },
    { label: 'DATASET', value: `${datasetMb.toFixed(1)} MB`, color: 'rgba(255,255,255,0.7)' },
    { label: 'FPS', value: fps.toFixed(1), color: 'rgba(255,255,255,0.7)' },
    { label: 'HAND', value: `L:${hasLeft ? '✓' : '–'}  R:${hasRight ? '✓' : '–'}`,
      color: (hasLeft || hasRight) ? '#22c55e' : 'rgba(255,255,255,0.4)' },
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
          label="HAND CAM"
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

// ─── Right rail: TankInputCard ──────────────────────────────────────────────
function TankInputCard({ steer, throttle }: { steer: number; throttle: number }) {
  return (
    <div style={card({ display: 'flex', flexDirection: 'column', gap: 12 })}>
      <Label>LIVE TANK INPUT</Label>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
      }}>
        <SteeringGauge value={steer} color={C1} />
        <ThrottleBar value={throttle} color={C1} />
      </div>
      <Divider />
      <KV label="STEER" value={steer >= 0 ? `+${steer.toFixed(3)}` : steer.toFixed(3)} color={C1} />
      <KV label="THROTTLE" value={throttle.toFixed(3)} color={C1} />
    </div>
  );
}

// ─── Right rail: LastSaveCard ──────────────────────────────────────────────
function LastSaveCard({ path }: { path: string }) {
  return (
    <div style={card({ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 4 })}>
      <Label>LAST SAVE</Label>
      <div style={{
        fontFamily: "var(--font-jetbrains-mono), monospace",
        fontSize: 10,
        color: 'rgba(255,255,255,0.55)',
        wordBreak: 'break-all',
      }}>
        {path}
      </div>
    </div>
  );
}
