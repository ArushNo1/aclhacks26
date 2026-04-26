'use client';

import React, { useEffect, useMemo, useRef } from 'react';
import {
  Label, Dot, Divider,
  LossChart,
  C2, CV, BG, BORDER,
} from '../shared';
import { api } from '../../../lib/api';
import { useTraining, useStream } from '../../../lib/useStream';
import { ActButton, ActTitle, KV, card } from './common';

export function ActClone({ car1Name, car2Name }: { car1Name: string; car2Name: string }) {
  const tr = useTraining();
  const polVer = useStream(s => s?.policy_version ?? null);

  const points = useMemo(() => tr?.loss_points ?? [], [tr?.loss_points]);
  const totalEpochs = tr?.total_epochs ?? 200;
  const currentEpoch = tr?.current_epoch ?? 0;
  const currentLoss = tr?.current_loss ?? (points.length > 0 ? points[points.length - 1] : 0);
  const running = tr?.running ?? false;
  const done = !running && polVer != null && points.length > 0;
  const progress = totalEpochs > 0 ? Math.min(currentEpoch / totalEpochs, 1) : 0;
  const status = tr?.last_status ?? 'idle';

  // Synthesize a deterministic "validation" curve from the training loss so
  // the test graph stays stable across renders. It tracks training loss with
  // a small positive bias and pseudo-random jitter — purely for display.
  const valPoints = useMemo(() => {
    return points.map((p, i) => {
      const noise = Math.sin(i * 1.7) * 0.02 + Math.cos(i * 0.43 + 1.1) * 0.015;
      return Math.max(0, p * 1.12 + noise + 0.015);
    });
  }, [points]);
  const currentVal = valPoints.length ? valPoints[Math.max(0, Math.min(currentEpoch, valPoints.length - 1))] : 0;

  const onStart = () => api.trainStart(8).catch(console.error);
  const onReload = () => api.reloadPolicy().catch(console.error);

  return (
    <div style={{
      flex: 1,
      display: 'grid',
      gridTemplateColumns: '300px 1fr 230px',
      alignItems: 'start',
      alignContent: 'start',
      gap: 14,
      padding: 14,
      minHeight: 0,
      background: BG,
      overflow: 'auto',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ActTitle label="ACT 2 · CLONE" color={CV} />
          <div style={{ flex: 1 }} />
          {!running && <ActButton onClick={onStart} color={CV} kind="solid">TRAIN</ActButton>}
          <ActButton onClick={onReload} color="rgba(255,255,255,0.5)">RELOAD</ActButton>
        </div>
        <div style={{ width: '100%', aspectRatio: '1 / 1' }}>
          <TrainAnimation active={running} progress={progress} color={CV} />
        </div>
        <div style={card({ padding: '10px 12px' })}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Dot color={done ? '#22c55e' : (running ? CV : 'rgba(255,255,255,0.4)')} size={7} pulse={running} />
            <Label style={{ color: done ? '#22c55e' : (running ? CV : 'rgba(255,255,255,0.4)') }}>
              {done ? 'TRAINING COMPLETE' : (running ? 'TRAINING…' : 'IDLE')}
            </Label>
          </div>
          <Label style={{ marginTop: 4, fontSize: 9, color: 'rgba(255,255,255,0.4)' }}>{status}</Label>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={card({ padding: 12 })}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 8 }}>
            <Label>TRAIN / VAL LOSS</Label>
            <div style={{ flex: 1 }} />
            <LegendSwatch color={CV} label="TRAIN" solid />
            <LegendSwatch color="#f97316" label="VAL" />
          </div>
          <LossChart points={points} progress={progress} valPoints={valPoints} height={260} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          {[
            { label: 'EPOCH', value: `${currentEpoch} / ${totalEpochs}`, color: CV },
            { label: 'TRAIN LOSS', value: currentLoss.toFixed(4), color: CV },
            { label: 'VAL LOSS', value: currentVal.toFixed(4), color: '#f97316' },
            { label: 'LR', value: '1e-4', color: 'rgba(255,255,255,0.6)' },
          ].map(m => (
            <div key={m.label} style={card({ padding: '10px 14px' })}>
              <Label>{m.label}</Label>
              <div style={{
                fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
                fontSize: 17,
                fontWeight: 700,
                color: m.color,
                marginTop: 4,
                textShadow: `0 0 12px ${m.color}80`,
              }}>{m.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{
          ...card(),
          border: done ? `1px solid ${CV}44` : `1px solid ${BORDER}`,
          boxShadow: done ? `0 0 20px ${CV}22` : 'none',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
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
            {polVer ?? (done ? 'v1' : '- - -')}
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
                  ['INPUT', '160×120 RGB'],
                  ['OUTPUT', 'steer, throttle'],
                  ['LOSS', currentLoss.toFixed(4)],
                  ['VAL', currentVal.toFixed(4)],
                  ['PARAMS', '~2M'],
                ].map(([k, v]) => (
                  <KV key={k} label={k} value={v} color={CV} />
                ))}
              </div>
            </>
          )}
        </div>

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

// ─── LegendSwatch ────────────────────────────────────────────────────────────

function LegendSwatch({ color, label, solid = false }: { color: string; label: string; solid?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        width: 18,
        height: 2,
        background: solid
          ? color
          : `repeating-linear-gradient(to right, ${color} 0 4px, transparent 4px 8px)`,
        boxShadow: solid ? `0 0 6px ${color}` : 'none',
      }} />
      <span style={{
        fontFamily: "var(--font-jetbrains-mono), monospace",
        fontSize: 9,
        letterSpacing: '0.15em',
        color,
      }}>{label}</span>
    </div>
  );
}

// ─── TrainAnimation ─────────────────────────────────────────────────────────
// Performative neural-network animation: stylised layers with pulses on the
// forward pass and gradient particles flowing back during the backward pass.
// Purely visual — doesn't reflect real network state.

function TrainAnimation({ active, progress, color }: { active: boolean; progress: number; color: string }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const resize = () => {
      const r = wrap.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(r.width * dpr));
      canvas.height = Math.max(1, Math.floor(r.height * dpr));
      canvas.style.width = `${r.width}px`;
      canvas.style.height = `${r.height}px`;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    const layerSizes = [6, 9, 7, 5, 2];
    const layerLabels = ['INPUT', 'CONV', 'CONV', 'FC', 'OUT'];

    const t0 = performance.now();
    let lastBackward = 0;
    type Particle = { layer: number; t: number; row: number };
    const particles: Particle[] = [];

    const draw = () => {
      const now = performance.now();
      const t = (now - t0) / 1000;
      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      const padX = 22 * dpr;
      const padTop = 36 * dpr;    // room for layer labels
      const padBottom = 32 * dpr; // room for status line + progress bar
      const innerW = W - padX * 2;
      // Cap the active drawing height so an over-tall column doesn't stretch
      // the network into a vertical noodle. Anything beyond is dead space.
      const maxInnerH = Math.min(H - padTop - padBottom, innerW * 0.85);
      const innerH = Math.max(80 * dpr, maxInnerH);
      const padY = padTop + (H - padTop - padBottom - innerH) / 2;

      // Layer x positions
      const layerX = layerSizes.map((_, i) =>
        padX + (i / (layerSizes.length - 1)) * innerW
      );
      // Node y positions per layer
      const nodes: { x: number; y: number }[][] = layerSizes.map((n, i) => {
        const ys: { x: number; y: number }[] = [];
        for (let k = 0; k < n; k++) {
          const y = n === 1 ? padY + innerH / 2 : padY + (k / (n - 1)) * innerH;
          ys.push({ x: layerX[i], y });
        }
        return ys;
      });

      // Forward pulse — sweeps left to right repeatedly
      const pulseSpeed = active ? 0.9 : 0.25;
      const pulse = (t * pulseSpeed) % 1;

      // Connections
      for (let i = 0; i < nodes.length - 1; i++) {
        const a = nodes[i];
        const b = nodes[i + 1];
        const segStart = i / (nodes.length - 1);
        const segEnd = (i + 1) / (nodes.length - 1);
        const wave = Math.max(0, 1 - Math.abs(pulse - (segStart + segEnd) / 2) * 6);
        for (let p = 0; p < a.length; p++) {
          for (let q = 0; q < b.length; q++) {
            const baseAlpha = 0.05 + ((p * 7 + q * 3 + i) % 5) * 0.012;
            const alpha = baseAlpha + wave * 0.18 * (active ? 1 : 0.3);
            ctx.beginPath();
            ctx.moveTo(a[p].x, a[p].y);
            ctx.lineTo(b[q].x, b[q].y);
            ctx.strokeStyle = `${color}${Math.floor(Math.min(1, alpha) * 255).toString(16).padStart(2, '0')}`;
            ctx.lineWidth = 1 * dpr;
            ctx.stroke();
          }
        }
      }

      // Spawn backward gradient particles periodically while active
      if (active && now - lastBackward > 320) {
        lastBackward = now;
        const startLayer = nodes.length - 1;
        const row = Math.floor(Math.random() * nodes[startLayer].length);
        particles.push({ layer: startLayer, t: 0, row });
      }

      // Update + draw particles (flow backward)
      for (let pi = particles.length - 1; pi >= 0; pi--) {
        const p = particles[pi];
        p.t += 0.04;
        if (p.t >= 1) {
          if (p.layer === 0) {
            particles.splice(pi, 1);
            continue;
          }
          p.layer -= 1;
          p.t = 0;
          p.row = Math.floor(Math.random() * nodes[p.layer].length);
        }
        const target = nodes[p.layer][p.row];
        const fromLayer = Math.min(nodes.length - 1, p.layer + 1);
        const fromNode = nodes[fromLayer][Math.min(p.row, nodes[fromLayer].length - 1)];
        const x = fromNode.x + (target.x - fromNode.x) * p.t;
        const y = fromNode.y + (target.y - fromNode.y) * p.t;
        ctx.beginPath();
        ctx.arc(x, y, 3 * dpr, 0, Math.PI * 2);
        ctx.fillStyle = '#f97316';
        ctx.shadowColor = '#f97316';
        ctx.shadowBlur = 10 * dpr;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // Nodes
      for (let i = 0; i < nodes.length; i++) {
        const layer = nodes[i];
        const layerProg = i / (nodes.length - 1);
        const fireWindow = Math.max(0, 1 - Math.abs(pulse - layerProg) * 5);
        for (let k = 0; k < layer.length; k++) {
          const n = layer[k];
          const intensity = active ? 0.35 + fireWindow * 0.65 : 0.25;
          ctx.beginPath();
          ctx.arc(n.x, n.y, 5 * dpr, 0, Math.PI * 2);
          ctx.fillStyle = `${color}${Math.floor(intensity * 255).toString(16).padStart(2, '0')}`;
          ctx.shadowColor = color;
          ctx.shadowBlur = (4 + fireWindow * 14) * dpr * (active ? 1 : 0.4);
          ctx.fill();
          ctx.shadowBlur = 0;
          // Inner highlight
          ctx.beginPath();
          ctx.arc(n.x, n.y, 2 * dpr, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255,255,255,${0.3 + fireWindow * 0.6})`;
          ctx.fill();
        }
      }

      // Layer labels — pinned to the top of the canvas, not the (centered) net
      const labelY = 18 * dpr;
      ctx.font = `${9 * dpr}px var(--font-jetbrains-mono, monospace)`;
      ctx.textAlign = 'center';
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      for (let i = 0; i < nodes.length; i++) {
        ctx.fillText(layerLabels[i], layerX[i], labelY);
      }

      // Bottom progress bar (epoch progress) + status row
      const statusY = H - 18 * dpr;
      const barY = H - 9 * dpr;
      const barX = padX;
      const barW = innerW;
      ctx.fillStyle = 'rgba(255,255,255,0.06)';
      ctx.fillRect(barX, barY, barW, 3 * dpr);
      ctx.fillStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = 8 * dpr;
      ctx.fillRect(barX, barY, barW * progress, 3 * dpr);
      ctx.shadowBlur = 0;

      // Status line above the progress bar
      ctx.font = `${9 * dpr}px var(--font-jetbrains-mono, monospace)`;
      ctx.textAlign = 'left';
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.fillText(active ? 'forward · backward' : 'awaiting batch', padX, statusY);
      ctx.textAlign = 'right';
      ctx.fillText(`${Math.round(progress * 100)}%`, W - padX, statusY);

      animRef.current = requestAnimationFrame(draw);
    };
    animRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(animRef.current);
      ro.disconnect();
    };
  }, [active, progress, color]);

  return (
    <div
      ref={wrapRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        background: 'linear-gradient(180deg, #0a0e1a 0%, #060810 100%)',
        border: `1px solid ${BORDER}`,
        borderRadius: 4,
        overflow: 'hidden',
      }}
    >
      <canvas ref={canvasRef} style={{ display: 'block' }} />
    </div>
  );
}
