'use client';

import React, { useEffect, useRef, useState } from 'react';
import { TopBar, SURFACE, BORDER, BG } from './shared';
import { ActCapture, ActClone, ActRace, ActDebug } from './acts/index';
import { api } from '../../lib/api';

interface Tweaks {
  car1Name: string;
  car2Name: string;
}

export type PovSource = 'sim' | 'car';

export default function Dashboard() {
  const [act, setAct] = useState(1);
  const [tweaks, setTweaks] = useState<Tweaks>({ car1Name: 'HUMAN_A', car2Name: 'HUMAN_B' });
  const [debugOpen, setDebugOpen] = useState(false);
  const [povSource, setPovSourceState] = useState<PovSource>('sim');

  const setPovSource = (next: PovSource) => {
    setPovSourceState(next);
    api.setPovSource(next).catch(err => {
      console.error('[pov] failed to set source', err);
    });
  };

  const views: Record<number, React.ReactNode> = {
    1: <ActCapture povSource={povSource} />,
    2: <ActClone car1Name={tweaks.car1Name} car2Name={tweaks.car2Name} />,
    3: <ActRace car1Name={tweaks.car1Name} car2Name={tweaks.car2Name} povSource={povSource} />,
  };

  const backendDown = useBackendDown();

  return (
    <>
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: BG }}>
        <TopBar act={act} onActChange={setAct} />
        <div key={act} className="gr-view">
          {views[act]}
        </div>
      </div>

      {backendDown && <BackendDownModal />}

      {/* Debug overlay */}
      {debugOpen && (
        <div
          onClick={() => setDebugOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.55)',
            zIndex: 200,
            display: 'flex',
            alignItems: 'stretch',
            justifyContent: 'flex-end',
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: 'min(1100px, 92vw)',
              height: '100%',
              background: BG,
              borderLeft: `1px solid ${BORDER}`,
              boxShadow: '-8px 0 40px rgba(0,0,0,0.7)',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <div style={{
              padding: '10px 14px',
              borderBottom: `1px solid ${BORDER}`,
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              flexShrink: 0,
              background: SURFACE,
            }}>
              <span style={{
                fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
                fontSize: 10,
                letterSpacing: '0.15em',
                color: 'rgba(255,255,255,0.6)',
              }}>DEBUG · TWEAKS</span>
              <PovSourceToggle value={povSource} onChange={setPovSource} />
              <div style={{ display: 'flex', gap: 12, flex: 1 }}>
                {(['car1Name', 'car2Name'] as const).map(key => (
                  <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <label style={{
                      fontFamily: "var(--font-jetbrains-mono), monospace",
                      fontSize: 9,
                      letterSpacing: '0.15em',
                      textTransform: 'uppercase' as const,
                      color: 'rgba(255,255,255,0.3)',
                    }}>
                      {key === 'car1Name' ? 'CAR 1' : 'CAR 2'}
                    </label>
                    <input
                      value={tweaks[key]}
                      onChange={e => setTweaks(prev => ({ ...prev, [key]: e.target.value }))}
                      style={{
                        background: 'rgba(255,255,255,0.05)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: 3,
                        padding: '4px 8px',
                        fontFamily: "var(--font-jetbrains-mono), monospace",
                        fontSize: 12,
                        color: '#fff',
                        outline: 'none',
                        width: 140,
                      }}
                    />
                  </div>
                ))}
              </div>
              <button
                onClick={() => setDebugOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'rgba(255,255,255,0.4)',
                  cursor: 'pointer',
                  fontSize: 16,
                  lineHeight: 1,
                  padding: 4,
                }}
              >✕</button>
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              <ActDebug />
            </div>
          </div>
        </div>
      )}

      {/* Settings toggle button */}
      <button
        onClick={() => setDebugOpen(o => !o)}
        style={{
          position: 'fixed',
          bottom: 20,
          right: 20,
          width: 36,
          height: 36,
          borderRadius: '50%',
          background: SURFACE,
          border: `1px solid rgba(255,255,255,0.15)`,
          color: 'rgba(255,255,255,0.5)',
          cursor: 'pointer',
          fontSize: 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 201,
        }}
      >
        ⚙
      </button>
    </>
  );
}

function PovSourceToggle({
  value,
  onChange,
}: {
  value: PovSource;
  onChange: (v: PovSource) => void;
}) {
  const opts: PovSource[] = ['sim', 'car'];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{
        fontFamily: "var(--font-jetbrains-mono), monospace",
        fontSize: 9,
        letterSpacing: '0.15em',
        textTransform: 'uppercase' as const,
        color: 'rgba(255,255,255,0.3)',
      }}>POV</span>
      <div style={{
        display: 'flex',
        background: 'rgba(255,255,255,0.05)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 3,
        padding: 2,
      }}>
        {opts.map(o => {
          const active = value === o;
          return (
            <button
              key={o}
              onClick={() => onChange(o)}
              style={{
                fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
                fontSize: 10,
                letterSpacing: '0.1em',
                padding: '4px 10px',
                borderRadius: 2,
                border: 'none',
                cursor: 'pointer',
                background: active ? 'rgba(255,255,255,0.12)' : 'transparent',
                color: active ? '#fff' : 'rgba(255,255,255,0.4)',
              }}
            >
              {o === 'sim' ? 'SIM' : 'CAR'}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Backend health detection ──────────────────────────────────────────────
// Polls /api/status. Marks backend as "down" only after MAX_FAILS consecutive
// failures so a single transient blip doesn't flash the modal. On a remote
// host (Vercel etc.) the backend is by definition unreachable — short-circuit
// to "down" immediately and skip polling.
function useBackendDown(): boolean {
  // On a remote host, start as "down" so the modal shows on first paint.
  const [down, setDown] = useState(() =>
    typeof window !== 'undefined' && !isLocalHost(window.location.host),
  );
  const failsRef = useRef(0);

  useEffect(() => {
    if (typeof window !== 'undefined' && !isLocalHost(window.location.host)) {
      return;
    }

    let cancelled = false;
    const MAX_FAILS = 3;

    const check = async () => {
      try {
        await api.status();
        if (cancelled) return;
        failsRef.current = 0;
        setDown(false);
      } catch {
        if (cancelled) return;
        failsRef.current += 1;
        if (failsRef.current >= MAX_FAILS) setDown(true);
      }
    };

    check();
    const id = setInterval(check, 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return down;
}

// localhost / 127.0.0.1 / ::1 / *.local — anywhere a local backend could
// actually be reached. Anything else (vercel.app, public DNS) is "remote".
function isLocalHost(host: string): boolean {
  if (!host) return false;
  const h = host.replace(/:\d+$/, '');
  return h === 'localhost' || h === '127.0.0.1' || h === '::1' || h.endsWith('.local');
}

// ─── Backend-down modal ────────────────────────────────────────────────────
function BackendDownModal() {
  const [copied, setCopied] = useState(false);
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000';
  const host = typeof window !== 'undefined' ? window.location.host : 'localhost:3000';
  const isRemote = !isLocalHost(host);

  // On a remote host (vercel.app etc.), `${origin}/install.sh` works because
  // install.sh is served from web/public — but the dashboard itself can't
  // reach the user's localhost backend, so we tell them to run it locally.
  const cmd = isRemote
    ? `curl -fsSL ${origin}/install.sh | bash && cd ghost-racer && ./run.sh`
    : `curl -fsSL ${origin}/install.sh | bash`;

  const copy = () => {
    navigator.clipboard?.writeText(cmd).then(
      () => { setCopied(true); setTimeout(() => setCopied(false), 1500); },
      () => { /* clipboard blocked — user can select manually */ },
    );
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.78)',
        zIndex: 300,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        backdropFilter: 'blur(6px)',
      }}
    >
      <div
        style={{
          width: 'min(640px, 100%)',
          background: SURFACE,
          border: `1px solid ${BORDER}`,
          borderRadius: 8,
          boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
          padding: 28,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            display: 'inline-block',
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: '#f43f5e',
            boxShadow: '0 0 10px #f43f5e',
          }} />
          <span style={{
            fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
            fontSize: 11,
            letterSpacing: '0.2em',
            color: '#f43f5e',
            fontWeight: 700,
          }}>
            {isRemote ? 'LOCAL-ONLY APP' : 'BACKEND OFFLINE'}
          </span>
        </div>

        <h2 style={{
          margin: 0,
          fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
          fontSize: 22,
          fontWeight: 700,
          color: '#fff',
          letterSpacing: '0.02em',
        }}>
          {isRemote
            ? 'this dashboard runs locally.'
            : 'uvicorn isn’t running.'}
        </h2>

        <p style={{
          margin: 0,
          fontFamily: "var(--font-jetbrains-mono), monospace",
          fontSize: 12,
          lineHeight: 1.6,
          color: 'rgba(255,255,255,0.65)',
        }}>
          {isRemote ? (
            <>
              ghost-racer talks to a Python backend, a webcam, and a physical car
              over MQTT — none of which can be reached from{' '}
              <code style={{ background: 'rgba(255,255,255,0.06)', padding: '1px 6px', borderRadius: 3 }}>{host}</code>.
              Clone, install, and run it on your own machine:
            </>
          ) : (
            <>
              The dashboard can&apos;t reach the Python backend at{' '}
              <code style={{ background: 'rgba(255,255,255,0.06)', padding: '1px 6px', borderRadius: 3 }}>localhost:8000</code>.
              Run this once to install, then start everything with{' '}
              <code style={{ background: 'rgba(255,255,255,0.06)', padding: '1px 6px', borderRadius: 3 }}>./run.sh</code>.
            </>
          )}
        </p>

        <div style={{
          position: 'relative',
          background: '#0a0e1a',
          border: `1px solid ${BORDER}`,
          borderRadius: 5,
          padding: '14px 16px',
          paddingRight: 80,
          fontFamily: "var(--font-jetbrains-mono), monospace",
          fontSize: 12,
          color: '#a5f3fc',
          wordBreak: 'break-all',
        }}>
          <span style={{ color: 'rgba(255,255,255,0.35)', userSelect: 'none' }}>$ </span>
          {cmd}
          <button
            onClick={copy}
            style={{
              position: 'absolute',
              top: 8,
              right: 8,
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: copied ? '#22c55e' : 'rgba(255,255,255,0.7)',
              fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
              fontSize: 9,
              letterSpacing: '0.18em',
              padding: '6px 10px',
              borderRadius: 3,
              cursor: 'pointer',
            }}
          >
            {copied ? 'COPIED' : 'COPY'}
          </button>
        </div>

        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          fontFamily: "var(--font-jetbrains-mono), monospace",
          fontSize: 11,
          color: 'rgba(255,255,255,0.5)',
          lineHeight: 1.6,
        }}>
          <span>{isRemote
            ? 'this clones the repo, sets up the venv, installs npm deps, and starts both servers.'
            : 'run.sh starts uvicorn (:8000) and the next dev server (:3000) together.'}</span>
          <span>then open{' '}
            <code style={{ color: 'rgba(255,255,255,0.85)' }}>http://localhost:3000</code>.
          </span>
        </div>

        <div style={{
          fontFamily: "var(--font-jetbrains-mono), monospace",
          fontSize: 10,
          color: 'rgba(255,255,255,0.35)',
          letterSpacing: '0.05em',
        }}>
          {isRemote
            ? 'this hosted page is just a landing card — it can’t connect to your machine.'
            : 'this dialog will close automatically once the server responds.'}
        </div>
      </div>
    </div>
  );
}
