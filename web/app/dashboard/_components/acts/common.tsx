'use client';

// Small helpers shared between the four acts. Visual primitives like
// CameraFeed, SteeringGauge, etc. still live in `../shared.tsx`.

import React, { CSSProperties } from 'react';
import { Label, SURFACE, BORDER } from '../shared';

// ─── ActTitle ────────────────────────────────────────────────────────────────
export function ActTitle({ label, color }: { label: string; color: string }) {
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

// ─── card() ──────────────────────────────────────────────────────────────────
export function card(extra: CSSProperties = {}): CSSProperties {
  return {
    background: SURFACE,
    border: `1px solid ${BORDER}`,
    borderRadius: 6,
    padding: 14,
    ...extra,
  };
}

// ─── KV row ─────────────────────────────────────────────────────────────────
export function KV({ label, value, color }: { label: string; value: string; color?: string }) {
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

// ─── small button ──────────────────────────────────────────────────────────
export function ActButton({
  onClick, color, children, kind = 'outline',
}: {
  onClick: () => void;
  color: string;
  children: React.ReactNode;
  kind?: 'outline' | 'solid';
}) {
  const solid = kind === 'solid';
  return (
    <button
      onClick={onClick}
      style={{
        background: solid ? `${color}22` : 'transparent',
        border: `1px solid ${solid ? color : `${color}55`}`,
        color,
        padding: '6px 14px',
        borderRadius: 4,
        cursor: 'pointer',
        fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
        fontSize: 10,
        letterSpacing: '0.2em',
        fontWeight: 700,
        transition: 'background 0.15s ease',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = `${color}33`)}
      onMouseLeave={(e) => (e.currentTarget.style.background = solid ? `${color}22` : 'transparent')}
    >
      {children}
    </button>
  );
}

// ─── time formatting ───────────────────────────────────────────────────────
export function fmtTime(s: number): string {
  return `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}`;
}

// ─── calibration anchor labels ──────────────────────────────────────────────
export const ANCHOR_LABEL: Record<string, string> = {
  neutral: 'NEUTRAL',
  forward: 'CLOSE TO CAMERA',
  backward: 'FAR FROM CAMERA',
};
