'use client';

import React, { useEffect, useRef, useState, CSSProperties } from 'react';
import { C1, C2, CV, BG, SURFACE, SURFACE2, BORDER, BORDER2 } from './tokens';

// ─── Hooks ────────────────────────────────────────────────────────────────────

export function useTick(ms = 16): number {
  const [t, setT] = useState(0);
  const start = useRef<number>(Date.now());
  useEffect(() => {
    const id = setInterval(() => {
      setT((Date.now() - start.current) / 1000);
    }, ms);
    return () => clearInterval(id);
  }, [ms]);
  return t;
}

export function useClock(): string {
  const [time, setTime] = useState('');
  useEffect(() => {
    const fmt = () => {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, '0');
      const mm = String(now.getMinutes()).padStart(2, '0');
      const ss = String(now.getSeconds()).padStart(2, '0');
      return `${hh}:${mm}:${ss}`;
    };
    setTime(fmt());
    const id = setInterval(() => setTime(fmt()), 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

export function useFrameCounter(active: boolean): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => {
      setCount(c => c + Math.floor(Math.random() * 15) + 6);
    }, 100);
    return () => clearInterval(id);
  }, [active]);
  return count;
}

// ─── Primitives ───────────────────────────────────────────────────────────────

export function Label({
  children,
  style,
  suppressHydrationWarning,
}: {
  children: React.ReactNode;
  style?: CSSProperties;
  suppressHydrationWarning?: boolean;
}) {
  return (
    <span
      suppressHydrationWarning={suppressHydrationWarning}
      style={{
        fontFamily: "var(--font-jetbrains-mono), 'JetBrains Mono', monospace",
        fontSize: 9,
        letterSpacing: '0.15em',
        textTransform: 'uppercase' as const,
        color: 'rgba(255,255,255,0.3)',
        ...style,
      }}
    >
      {children}
    </span>
  );
}

export function BigNum({
  value,
  size = 48,
  color = '#fff',
  unit,
  style,
}: {
  value: string | number;
  size?: number;
  color?: string;
  unit?: string;
  style?: CSSProperties;
}) {
  return (
    <span style={{
      fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
      fontWeight: 700,
      fontSize: size,
      color,
      textShadow: `0 0 20px ${color}80`,
      lineHeight: 1,
      ...style,
    }}>
      {value}
      {unit && (
        <span style={{ fontSize: size * 0.45, opacity: 0.6, marginLeft: 4 }}>{unit}</span>
      )}
    </span>
  );
}

export function Dot({
  color,
  size = 8,
  pulse = false,
  style,
}: {
  color: string;
  size?: number;
  pulse?: boolean;
  style?: CSSProperties;
}) {
  return (
    <span style={{
      display: 'inline-block',
      width: size,
      height: size,
      borderRadius: '50%',
      background: color,
      boxShadow: `0 0 ${size}px ${color}`,
      flexShrink: 0,
      animation: pulse ? 'gr-pulse 1.2s ease-in-out infinite' : undefined,
      ...style,
    }} />
  );
}

export function Divider({ vertical = false, style }: { vertical?: boolean; style?: CSSProperties }) {
  return (
    <span style={{
      display: 'block',
      ...(vertical
        ? { width: 1, alignSelf: 'stretch', background: BORDER2 }
        : { height: 1, width: '100%', background: BORDER2 }),
      flexShrink: 0,
      ...style,
    }} />
  );
}

// ─── CameraFeed ───────────────────────────────────────────────────────────────

export function CameraFeed({
  color,
  label,
  mode = 'manual',
  style,
  src,
  resolution,
}: {
  color: string;
  label: string;
  mode?: 'manual' | 'auto';
  style?: CSSProperties;
  /** Optional MJPEG / image URL. When provided, the synthetic canvas is
   *  replaced with a live <img> stream and the canvas animation is skipped. */
  src?: string;
  /** Resolution label rendered in the bottom-right HUD. */
  resolution?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const phaseRef = useRef<number>(0);
  const swayRef = useRef<number>(0);

  useEffect(() => {
    if (src) return; // live MJPEG mode — no canvas animation
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let lastTime = 0;

    const draw = (ts: number) => {
      const dt = Math.min((ts - lastTime) / 1000, 0.05);
      lastTime = ts;
      phaseRef.current += dt;
      const phase = phaseRef.current;

      const swayAmp = mode === 'auto' ? 0.012 : 0.032;
      swayRef.current += (Math.sin(phase * 0.7) * swayAmp - swayRef.current) * 0.08;
      const sway = swayRef.current;

      const W = canvas.width;
      const H = canvas.height;

      // Sky gradient
      const skyGrad = ctx.createLinearGradient(0, 0, 0, H * 0.55);
      skyGrad.addColorStop(0, '#080c18');
      skyGrad.addColorStop(1, '#0e1830');
      ctx.fillStyle = skyGrad;
      ctx.fillRect(0, 0, W, H);

      // Road trapezoid
      const vanX = W / 2 + sway * W;
      const vanY = H * 0.48;
      ctx.beginPath();
      ctx.moveTo(0, H);
      ctx.lineTo(W, H);
      ctx.lineTo(W * 0.78, vanY);
      ctx.lineTo(W * 0.22, vanY);
      ctx.closePath();
      const roadGrad = ctx.createLinearGradient(0, H, 0, vanY);
      roadGrad.addColorStop(0, '#1a1a2e');
      roadGrad.addColorStop(1, '#0d1020');
      ctx.fillStyle = roadGrad;
      ctx.fill();

      // Color bleed on road
      const bleedGrad = ctx.createRadialGradient(vanX, H, 0, vanX, H, W * 0.8);
      bleedGrad.addColorStop(0, color + '22');
      bleedGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = bleedGrad;
      ctx.fillRect(0, 0, W, H);

      // Center dashes
      const dashCount = 6;
      for (let i = 0; i < dashCount; i++) {
        const prog = ((i / dashCount + phase * 0.4) % 1);
        const y1 = vanY + (H - vanY) * prog;
        const y2 = vanY + (H - vanY) * Math.min(prog + 0.08, 1);
        const xCenter = vanX + (W / 2 - vanX) * (1 - (y1 - vanY) / (H - vanY));
        const halfW = 3 + (y1 - vanY) / (H - vanY) * 6;
        ctx.beginPath();
        ctx.moveTo(xCenter - halfW, y1);
        ctx.lineTo(xCenter + halfW, y1);
        ctx.lineTo(xCenter + halfW, y2);
        ctx.lineTo(xCenter - halfW, y2);
        ctx.closePath();
        ctx.fillStyle = `rgba(255,255,255,${0.15 + prog * 0.2})`;
        ctx.fill();
      }

      // Car silhouette
      const carX = W / 2 + sway * W * 0.3;
      const carY = H * 0.78;
      const carW = W * 0.28;
      const carH = H * 0.09;
      ctx.shadowColor = color;
      ctx.shadowBlur = 18;
      ctx.fillStyle = '#0a0e1a';
      ctx.beginPath();
      ctx.rect(carX - carW / 2, carY, carW, carH);
      ctx.fill();
      // Cabin
      ctx.beginPath();
      ctx.rect(carX - carW * 0.3, carY - carH * 0.7, carW * 0.6, carH * 0.7);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Glow under car
      const glowGrad = ctx.createRadialGradient(carX, carY + carH, 0, carX, carY + carH, carW * 0.7);
      glowGrad.addColorStop(0, color + '55');
      glowGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = glowGrad;
      ctx.fillRect(carX - carW, carY, carW * 2, carH * 2);

      // Scanlines
      for (let y = 0; y < H; y += 3) {
        ctx.fillStyle = 'rgba(0,0,0,0.08)';
        ctx.fillRect(0, y, W, 1);
      }

      // Vignette
      const vigGrad = ctx.createRadialGradient(W / 2, H / 2, H * 0.2, W / 2, H / 2, H * 0.8);
      vigGrad.addColorStop(0, 'transparent');
      vigGrad.addColorStop(1, 'rgba(0,0,0,0.65)');
      ctx.fillStyle = vigGrad;
      ctx.fillRect(0, 0, W, H);

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  }, [color, mode, src]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', borderRadius: 4, ...style }}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={label}
          style={{
            width: '100%',
            height: '100%',
            display: 'block',
            objectFit: 'cover',
            background: '#0a0e1a',
          }}
        />
      ) : (
        <canvas
          ref={canvasRef}
          width={640}
          height={400}
          style={{ width: '100%', height: '100%', display: 'block', objectFit: 'cover' }}
        />
      )}
      {/* Top HUD */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0,
        padding: '6px 10px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.7), transparent)',
      }}>
        <Label style={{ color: color, fontSize: 10 }}>{label}</Label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Dot color="#ff3333" size={6} pulse />
          <Label style={{ color: '#ff3333', fontSize: 10 }}>LIVE</Label>
        </div>
      </div>
      {/* Bottom HUD */}
      <div style={{
        position: 'absolute',
        bottom: 0, left: 0, right: 0,
        padding: '6px 10px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'linear-gradient(to top, rgba(0,0,0,0.7), transparent)',
      }}>
        <Label suppressHydrationWarning style={{ fontSize: 9 }}>
          REC {new Date().toISOString().slice(11, 19)}
        </Label>
        <Label style={{ fontSize: 9 }}>{resolution ?? '640×480'}</Label>
      </div>
    </div>
  );
}

// ─── SteeringGauge ────────────────────────────────────────────────────────────

export function SteeringGauge({ value, color }: { value: number; color: string }) {
  const SIZE = 130;
  const cx = SIZE / 2;
  const cy = SIZE / 2;
  const r = 50;
  const strokeW = 7;
  const startAngle = Math.PI * 0.75;
  const endAngle = Math.PI * 2.25;
  const totalArc = endAngle - startAngle;

  const polarX = (angle: number) => cx + r * Math.cos(angle);
  const polarY = (angle: number) => cy + r * Math.sin(angle);

  // Background arc path
  const bgD = describeArc(cx, cy, r, startAngle, endAngle);

  // Active arc: from center (startAngle + half) to current value
  const midAngle = startAngle + totalArc / 2;
  const clampedVal = Math.max(-1, Math.min(1, value));
  const activeAngle = midAngle + clampedVal * (totalArc / 2);
  const [arcStart, arcEnd] = clampedVal >= 0
    ? [midAngle, activeAngle]
    : [activeAngle, midAngle];

  const activeD = Math.abs(clampedVal) > 0.01
    ? describeArc(cx, cy, r, arcStart, arcEnd)
    : '';

  // Needle dot
  const needleAngle = midAngle + clampedVal * (totalArc / 2);
  const nx = polarX(needleAngle);
  const ny = polarY(needleAngle);

  return (
    <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
      {/* Background track */}
      <path d={bgD} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={strokeW} strokeLinecap="round" />
      {/* Active arc */}
      {activeD && (
        <path
          d={activeD}
          fill="none"
          stroke={color}
          strokeWidth={strokeW}
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 4px ${color})` }}
        />
      )}
      {/* Needle dot */}
      <circle cx={nx} cy={ny} r={5} fill={color} style={{ filter: `drop-shadow(0 0 5px ${color})` }} />
      {/* Center dot */}
      <circle cx={cx} cy={cy} r={8} fill={SURFACE2} stroke={color + '80'} strokeWidth={1.5} />
      {/* Value text */}
      <text
        x={cx}
        y={cy + 22}
        textAnchor="middle"
        fill="rgba(255,255,255,0.7)"
        fontSize={10}
        fontFamily="var(--font-jetbrains-mono), monospace"
      >
        {value >= 0 ? '+' : ''}{value.toFixed(2)}
      </text>
      {/* L/R labels */}
      <text
        x={polarX(startAngle) - 6}
        y={polarY(startAngle) + 4}
        textAnchor="middle"
        fill="rgba(255,255,255,0.25)"
        fontSize={8}
        fontFamily="var(--font-jetbrains-mono), monospace"
      >L</text>
      <text
        x={polarX(endAngle) + 6}
        y={polarY(endAngle) + 4}
        textAnchor="middle"
        fill="rgba(255,255,255,0.25)"
        fontSize={8}
        fontFamily="var(--font-jetbrains-mono), monospace"
      >R</text>
    </svg>
  );
}

function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
  const x1 = cx + r * Math.cos(startAngle);
  const y1 = cy + r * Math.sin(startAngle);
  const x2 = cx + r * Math.cos(endAngle);
  const y2 = cy + r * Math.sin(endAngle);
  const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
}

// ─── ThrottleBar ─────────────────────────────────────────────────────────────

export function ThrottleBar({ value, color }: { value: number; color: string }) {
  const W = 22;
  const H = 110;
  const fill = Math.max(0, Math.min(1, value));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
      <div style={{
        width: W,
        height: H,
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 3,
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Fill */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: `${fill * 100}%`,
          background: `linear-gradient(to top, ${color}, ${color}88)`,
          boxShadow: `0 0 10px ${color}88`,
          transition: 'height 0.08s linear',
        }} />
        {/* Tick marks */}
        {[0.25, 0.5, 0.75].map(tick => (
          <div key={tick} style={{
            position: 'absolute',
            bottom: `${tick * 100}%`,
            left: 0,
            right: 0,
            height: 1,
            background: 'rgba(255,255,255,0.15)',
          }} />
        ))}
      </div>
      <Label>{Math.round(fill * 100)}%</Label>
    </div>
  );
}

// ─── RaceLights ───────────────────────────────────────────────────────────────

export function RaceLights({ phase }: { phase: 'off' | 'red' | 'yellow' | 'green' }) {
  const lights: Array<{ color: string; active: boolean }> = [
    { color: '#ff2020', active: phase === 'red' || phase === 'yellow' || phase === 'green' },
    { color: '#ffcc00', active: phase === 'yellow' || phase === 'green' },
    { color: '#22c55e', active: phase === 'green' },
  ];

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      {lights.map((l, i) => (
        <div key={i} style={{
          width: 18,
          height: 18,
          borderRadius: '50%',
          background: l.active ? l.color : 'rgba(255,255,255,0.06)',
          boxShadow: l.active ? `0 0 12px ${l.color}, 0 0 24px ${l.color}66` : 'none',
          transition: 'all 0.15s ease',
        }} />
      ))}
    </div>
  );
}

// ─── TrackMap ─────────────────────────────────────────────────────────────────

export function TrackMap({ car1T, car2T }: { car1T: number; car2T: number }) {
  const W = 300;
  const H = 180;
  const cx = 150;
  const cy = 90;
  const rx = 118;
  const ry = 62;

  const carPos = (t: number) => {
    const angle = t * Math.PI * 2 - Math.PI / 2;
    return {
      x: cx + rx * Math.cos(angle),
      y: cy + ry * Math.sin(angle),
    };
  };

  const c1 = carPos(car1T);
  const c2 = carPos(car2T);

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      {/* Track surface */}
      <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={18} />
      {/* Outer outline */}
      <ellipse cx={cx} cy={cy} rx={rx + 9} ry={ry + 9} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth={1} />
      {/* Inner outline + fill */}
      <ellipse cx={cx} cy={cy} rx={rx - 9} ry={ry - 9} fill="rgba(255,255,255,0.02)" stroke="rgba(255,255,255,0.08)" strokeWidth={1} />
      {/* Circuit label */}
      <text x={cx} y={cy + 5} textAnchor="middle" fill="rgba(255,255,255,0.12)"
        fontSize={11} fontFamily="var(--font-orbitron), sans-serif" letterSpacing="0.2em">
        CIRCUIT
      </text>
      {/* Start/finish line at top */}
      <line x1={cx - 3} y1={cy - ry - 9} x2={cx + 3} y2={cy - ry + 9} stroke="rgba(255,255,255,0.4)" strokeWidth={2} />
      {/* Car 1 */}
      <circle cx={c1.x} cy={c1.y} r={9} fill={C1 + '22'} />
      <circle cx={c1.x} cy={c1.y} r={5} fill={C1} style={{ filter: `drop-shadow(0 0 5px ${C1})` }} />
      <text x={c1.x + 9} y={c1.y + 4} fill={C1} fontSize={8} fontFamily="var(--font-jetbrains-mono), monospace">C1</text>
      {/* Car 2 */}
      <circle cx={c2.x} cy={c2.y} r={9} fill={C2 + '22'} />
      <circle cx={c2.x} cy={c2.y} r={5} fill={C2} style={{ filter: `drop-shadow(0 0 5px ${C2})` }} />
      <text x={c2.x + 9} y={c2.y + 4} fill={C2} fontSize={8} fontFamily="var(--font-jetbrains-mono), monospace">C2</text>
    </svg>
  );
}

// ─── LossChart ────────────────────────────────────────────────────────────────

export function LossChart({
  points,
  progress,
  valPoints,
  color,
  height = 200,
}: {
  points: number[];
  progress: number;
  /** Optional second series rendered as a dashed line (e.g. validation/test loss). */
  valPoints?: number[];
  /** Primary line color. Defaults to CV. */
  color?: string;
  /** Canvas display height in px. */
  height?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const lineColor = color ?? CV;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const visible = Math.max(2, Math.floor(progress * points.length));
    const visiblePts = points.slice(0, visible);
    const visibleVal = valPoints ? valPoints.slice(0, visible) : null;

    ctx.clearRect(0, 0, W, H);

    const padL = 40;
    const padB = 28;
    const padT = 12;
    const padR = 12;
    const chartW = W - padL - padR;
    const chartH = H - padT - padB;

    const maxY = Math.max(
      ...visiblePts,
      ...(visibleVal ?? []),
      0.5,
    );
    const minY = 0;

    const toX = (i: number) => padL + (i / (points.length - 1)) * chartW;
    const toY = (v: number) => padT + chartH - ((v - minY) / (maxY - minY)) * chartH;

    // Grid lines
    for (let i = 0; i <= 5; i++) {
      const y = padT + (i / 5) * chartH;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(padL + chartW, y);
      ctx.strokeStyle = 'rgba(255,255,255,0.05)';
      ctx.lineWidth = 1;
      ctx.stroke();
      const val = maxY - (i / 5) * (maxY - minY);
      ctx.fillStyle = 'rgba(255,255,255,0.25)';
      ctx.font = `10px var(--font-jetbrains-mono, monospace)`;
      ctx.textAlign = 'right';
      ctx.fillText(val.toFixed(2), padL - 5, y + 4);
    }

    // Axis lines
    ctx.beginPath();
    ctx.moveTo(padL, padT);
    ctx.lineTo(padL, padT + chartH);
    ctx.lineTo(padL + chartW, padT + chartH);
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.lineWidth = 1;
    ctx.stroke();

    // EPOCHS label
    ctx.fillStyle = 'rgba(255,255,255,0.2)';
    ctx.font = `9px var(--font-jetbrains-mono, monospace)`;
    ctx.textAlign = 'center';
    ctx.fillText('EPOCHS →', padL + chartW / 2, H - 4);

    if (visiblePts.length < 2) return;

    // Gradient fill
    const grad = ctx.createLinearGradient(0, padT, 0, padT + chartH);
    grad.addColorStop(0, lineColor + '60');
    grad.addColorStop(1, lineColor + '00');

    ctx.beginPath();
    ctx.moveTo(toX(0), toY(visiblePts[0]));
    for (let i = 1; i < visiblePts.length; i++) {
      ctx.lineTo(toX(i), toY(visiblePts[i]));
    }
    ctx.lineTo(toX(visiblePts.length - 1), padT + chartH);
    ctx.lineTo(toX(0), padT + chartH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Validation line (dashed, drawn beneath the main glow line)
    if (visibleVal && visibleVal.length >= 2) {
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(toX(0), toY(visibleVal[0]));
      for (let i = 1; i < visibleVal.length; i++) {
        ctx.lineTo(toX(i), toY(visibleVal[i]));
      }
      ctx.strokeStyle = '#f97316';
      ctx.lineWidth = 1.5;
      ctx.shadowColor = '#f97316';
      ctx.shadowBlur = 6;
      ctx.stroke();
      ctx.restore();
    }

    // Glowing line
    ctx.beginPath();
    ctx.moveTo(toX(0), toY(visiblePts[0]));
    for (let i = 1; i < visiblePts.length; i++) {
      ctx.lineTo(toX(i), toY(visiblePts[i]));
    }
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.shadowColor = lineColor;
    ctx.shadowBlur = 8;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Cursor dot
    const lastX = toX(visiblePts.length - 1);
    const lastY = toY(visiblePts[visiblePts.length - 1]);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = lineColor;
    ctx.shadowColor = lineColor;
    ctx.shadowBlur = 12;
    ctx.fill();
    ctx.shadowBlur = 0;
  }, [points, progress, valPoints, lineColor]);

  return (
    <canvas
      ref={canvasRef}
      width={520}
      height={height * 1}
      style={{ width: '100%', height, display: 'block' }}
    />
  );
}

// ─── MQTT Log ────────────────────────────────────────────────────────────────

import { useMqttLog } from '../../lib/useMqttLog';

function topicColor(topic: string): string {
  if (topic.startsWith('car/1')) return C1;
  if (topic.startsWith('car/2')) return C2;
  if (topic.startsWith('race')) return '#22c55e';
  if (topic.startsWith('trainer') || topic.startsWith('leap')) return '#8b5cf6';
  if (topic.startsWith('device')) return '#eab308';
  return 'rgba(255,255,255,0.6)';
}

function fmtMqttTs(ts: number): string {
  const d = new Date(ts * 1000);
  const pad2 = (n: number) => String(n).padStart(2, '0');
  const pad3 = (n: number) => String(n).padStart(3, '0');
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}.${pad3(d.getMilliseconds())}`;
}

export function MQTTLog() {
  const records = useMqttLog();
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [records]);

  return (
    <div
      ref={listRef}
      style={{
        flex: 1,
        overflow: 'auto',
        fontFamily: "var(--font-jetbrains-mono), 'JetBrains Mono', monospace",
        fontSize: 11,
        lineHeight: 1.7,
        padding: '8px 12px',
      }}
    >
      {records.length === 0 && (
        <div style={{ color: 'rgba(255,255,255,0.3)', fontStyle: 'italic' as const }}>
          Waiting for MQTT messages on car/+/+, race/+, device/+/+, leap/+, trainer/+ …
        </div>
      )}
      {records.map((e, i) => (
        <div key={i + ':' + e.ts} style={{ display: 'flex', gap: 10, whiteSpace: 'nowrap' }}>
          <span style={{ color: 'rgba(255,255,255,0.25)', flexShrink: 0 }}>{fmtMqttTs(e.ts)}</span>
          <span style={{ color: topicColor(e.topic), flexShrink: 0, minWidth: 160 }}>{e.topic}</span>
          <span style={{ color: 'rgba(255,255,255,0.55)', overflow: 'hidden', textOverflow: 'ellipsis' as const }}>{e.payload}</span>
        </div>
      ))}
    </div>
  );
}

// ─── DeviceHealth ─────────────────────────────────────────────────────────────

export function DeviceHealth() {
  type Device = { name: string; sub: string; metrics: Record<string, string> };
  const [devices, setDevices] = useState<Device[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const res = await fetch('/api/health');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json() as { devices: Device[] };
        if (!cancelled) {
          setDevices(data.devices);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    };
    refresh();
    const id = setInterval(refresh, 2500);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (err && devices.length === 0) {
    return <div style={{
      color: 'rgba(255,255,255,0.4)',
      fontFamily: "var(--font-jetbrains-mono), monospace",
      fontSize: 11,
    }}>health unavailable: {err}</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {devices.map(d => (
        <div key={d.name} style={{
          background: SURFACE,
          border: `1px solid ${BORDER}`,
          borderRadius: 4,
          padding: '8px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <Dot color="#22c55e" size={7} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontFamily: "var(--font-space-grotesk), 'Space Grotesk', sans-serif",
              fontSize: 12,
              fontWeight: 500,
              color: 'rgba(255,255,255,0.85)',
            }}>{d.name}</div>
            <div style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: 9,
              color: 'rgba(255,255,255,0.3)',
            }}>{d.sub}</div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            {Object.entries(d.metrics).map(([k, v]) => (
              <div key={k} style={{ textAlign: 'right' }}>
                <div style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: 10,
                  color: 'rgba(255,255,255,0.7)',
                }}>{v}</div>
                <div style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: 8,
                  color: 'rgba(255,255,255,0.25)',
                }}>{k}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── TopBar ───────────────────────────────────────────────────────────────────

const ACT_CONFIG: Array<{ label: string; color: string }> = [
  { label: 'CAPTURE', color: C1 },
  { label: 'CLONE', color: CV },
  { label: 'RACE', color: C2 },
  { label: 'DEBUG', color: 'rgba(255,255,255,0.4)' },
];

export function TopBar({ act, onActChange }: { act: number; onActChange: (n: number) => void }) {
  const clock = useClock();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const n = parseInt(e.key);
      if (n >= 1 && n <= 4) onActChange(n);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onActChange]);

  return (
    <div style={{
      height: 52,
      background: SURFACE,
      borderBottom: `1px solid ${BORDER2}`,
      display: 'flex',
      alignItems: 'center',
      padding: '0 16px',
      gap: 16,
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <span style={{
          fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
          fontWeight: 900,
          fontSize: 14,
          background: `linear-gradient(90deg, ${C1}, ${CV}, ${C2})`,
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          letterSpacing: '0.08em',
        }}>
          GHOST RACER
        </span>
        <Divider vertical style={{ height: 20 }} />
        <Label>MISSION CONTROL</Label>
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Act buttons */}
      <div style={{ display: 'flex', gap: 4 }}>
        {ACT_CONFIG.map((cfg, i) => {
          const n = i + 1;
          const active = act === n;
          return (
            <button
              key={n}
              onClick={() => onActChange(n)}
              style={{
                fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: '0.1em',
                padding: '5px 12px',
                borderRadius: 3,
                cursor: 'pointer',
                border: active ? `1px solid ${cfg.color}` : '1px solid transparent',
                background: active ? cfg.color + '22' : 'transparent',
                color: active ? cfg.color : 'rgba(255,255,255,0.3)',
                transition: 'all 0.15s',
              }}
            >
              {n} · {cfg.label}
            </button>
          );
        })}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Right side */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Dot color="#22c55e" size={7} pulse />
          <Label style={{ color: '#22c55e' }}>CONNECTED</Label>
        </div>
        <Divider vertical style={{ height: 20 }} />
        <span style={{
          fontFamily: "var(--font-jetbrains-mono), 'JetBrains Mono', monospace",
          fontSize: 12,
          color: 'rgba(255,255,255,0.5)',
          letterSpacing: '0.05em',
        }}>
          {clock}
        </span>
      </div>
    </div>
  );
}

// re-export tokens for use in acts
export { C1, C2, CV, BG, SURFACE, SURFACE2, BORDER, BORDER2 };
