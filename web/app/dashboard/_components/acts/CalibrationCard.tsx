'use client';

import React from 'react';
import { Label, Dot, Divider, C1, SURFACE2 } from '../shared';
import { ActButton, ANCHOR_LABEL, card } from './common';
import type { HandCalibrationStatus, HandProfile } from '../../../lib/api';

export function CalibrationCard({
  attached,
  calibrated,
  calibration,
  profile,
  onStart,
  onCapture,
  onRedo,
  onCancel,
  onReset,
}: {
  attached: boolean;
  calibrated: boolean;
  calibration: HandCalibrationStatus | undefined;
  profile: HandProfile | null;
  onStart: () => void;
  onCapture: () => void;
  onRedo: () => void;
  onCancel: () => void;
  onReset: () => void;
}) {
  const active = calibration?.active ?? false;
  const completed = calibration?.completed ?? false;
  const step = calibration?.step ?? null;
  const error = calibration?.error ?? null;
  const lastCaptured = calibration?.last_captured_size ?? null;

  let stateLabel: string;
  let stateColor: string;
  if (!attached) { stateLabel = 'NO WEBCAM'; stateColor = 'rgba(255,255,255,0.4)'; }
  else if (active && step) { stateLabel = `STEP ${step.index} / ${step.total}`; stateColor = C1; }
  else if (completed) { stateLabel = 'CALIBRATED'; stateColor = '#22c55e'; }
  else if (calibrated) { stateLabel = 'PROFILE LOADED'; stateColor = '#22c55e'; }
  else { stateLabel = 'NOT CALIBRATED'; stateColor = '#eab308'; }

  return (
    <div style={card({ display: 'flex', flexDirection: 'column', gap: 10 })}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Label>HAND RECORDER</Label>
        <div style={{ flex: 1 }} />
        <Dot color={stateColor} size={7} pulse={active} />
        <Label style={{ color: stateColor }}>{stateLabel}</Label>
      </div>
      <Divider />

      {!attached && (
        <div style={msgStyle}>
          Connect a webcam on the server host and restart the backend to enable
          hand calibration + recording.
        </div>
      )}

      {attached && active && step && (
        <>
          <div style={{
            fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
            fontSize: 12,
            fontWeight: 700,
            color: step.target === 'L' ? '#0ea5e9' : '#22c55e',
            letterSpacing: '0.1em',
          }}>
            {step.target === 'L' ? 'LEFT HAND' : 'RIGHT HAND'} · {ANCHOR_LABEL[step.anchor] ?? step.anchor.toUpperCase()}
          </div>
          <div style={msgStyle}>{step.prompt}</div>
          {lastCaptured !== null && (
            <div style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: 10,
              color: 'rgba(255,255,255,0.45)',
            }}>
              last captured size: {lastCaptured.toFixed(3)}
            </div>
          )}
          {error && (
            <div style={{ ...msgStyle, color: '#f87171' }}>{error}</div>
          )}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>
            <ActButton onClick={onCapture} color="#22c55e" kind="solid">CAPTURE</ActButton>
            <ActButton onClick={onRedo} color="rgba(255,255,255,0.5)">REDO</ActButton>
            <div style={{ flex: 1 }} />
            <ActButton onClick={onCancel} color="#f87171">CANCEL</ActButton>
          </div>
        </>
      )}

      {attached && !active && (
        <>
          {profile && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '4px 0' }}>
              <ProfileRow label="L  N / + / −" values={[profile.left_neutral_size, profile.left_forward_size, profile.left_backward_size]} color="#0ea5e9" />
              <ProfileRow label="R  N / + / −" values={[profile.right_neutral_size, profile.right_forward_size, profile.right_backward_size]} color="#22c55e" />
            </div>
          )}
          {!profile && (
            <div style={msgStyle}>
              No saved profile. Run the 6-step calibration to map each hand&apos;s
              neutral / close / far positions to throttle.
            </div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <ActButton onClick={onStart} color={C1} kind="solid">
              {profile ? 'RECALIBRATE' : 'CALIBRATE'}
            </ActButton>
            {profile && (
              <ActButton onClick={onReset} color="rgba(255,255,255,0.4)">FORGET</ActButton>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function ProfileRow({ label, values, color }: { label: string; values: number[]; color: string }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      fontFamily: "var(--font-jetbrains-mono), monospace",
      fontSize: 11,
    }}>
      <span style={{ color, minWidth: 90 }}>{label}</span>
      <span style={{ color: 'rgba(255,255,255,0.7)' }}>
        {values.map(v => v.toFixed(2)).join(' / ')}
      </span>
    </div>
  );
}

const msgStyle: React.CSSProperties = {
  fontFamily: "var(--font-jetbrains-mono), monospace",
  fontSize: 11,
  color: 'rgba(255,255,255,0.65)',
  lineHeight: 1.55,
};

// re-export so consumers don't need to dig for it
export { SURFACE2 };
