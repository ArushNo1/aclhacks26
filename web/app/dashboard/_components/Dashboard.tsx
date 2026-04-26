'use client';

import React, { useState } from 'react';
import { TopBar, SURFACE, BORDER, BG } from './shared';
import { ActCapture, ActClone, ActRace, ActDebug } from './acts/index';

interface Tweaks {
  car1Name: string;
  car2Name: string;
}

export type PovSource = 'sim' | 'car';

export default function Dashboard() {
  const [act, setAct] = useState(1);
  const [tweaks, setTweaks] = useState<Tweaks>({ car1Name: 'HUMAN_A', car2Name: 'HUMAN_B' });
  const [debugOpen, setDebugOpen] = useState(false);
  const [povSource, setPovSource] = useState<PovSource>('sim');

  const views: Record<number, React.ReactNode> = {
    1: <ActCapture povSource={povSource} />,
    2: <ActClone car1Name={tweaks.car1Name} car2Name={tweaks.car2Name} />,
    3: <ActRace car1Name={tweaks.car1Name} car2Name={tweaks.car2Name} />,
  };

  return (
    <>
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: BG }}>
        <TopBar act={act} onActChange={setAct} />
        <div key={act} className="gr-view">
          {views[act]}
        </div>
      </div>

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
