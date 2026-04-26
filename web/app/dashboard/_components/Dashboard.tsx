'use client';

import React, { useState } from 'react';
import { TopBar, SURFACE, BORDER } from './shared';
import { ActCapture, ActClone, ActRace, ActDebug } from './acts';

interface Tweaks {
  car1Name: string;
  car2Name: string;
}

export default function Dashboard() {
  const [act, setAct] = useState(1);
  const [tweaks, setTweaks] = useState<Tweaks>({ car1Name: 'HUMAN_A', car2Name: 'HUMAN_B' });
  const [tweaksOpen, setTweaksOpen] = useState(false);

  const views: Record<number, React.ReactNode> = {
    1: <ActCapture />,
    2: <ActClone car1Name={tweaks.car1Name} car2Name={tweaks.car2Name} />,
    3: <ActRace car1Name={tweaks.car1Name} car2Name={tweaks.car2Name} />,
    4: <ActDebug />,
  };

  return (
    <>
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: '#060810' }}>
        <TopBar act={act} onActChange={setAct} />
        <div key={act} className="gr-view">
          {views[act]}
        </div>
      </div>

      {/* Tweaks panel */}
      {tweaksOpen && (
        <div style={{
          position: 'fixed',
          bottom: 20,
          right: 20,
          width: 260,
          background: SURFACE,
          border: `1px solid rgba(255,255,255,0.12)`,
          borderRadius: 6,
          zIndex: 200,
          boxShadow: '0 8px 40px rgba(0,0,0,0.7)',
          overflow: 'hidden',
        }}>
          {/* Header */}
          <div style={{
            padding: '10px 14px',
            borderBottom: `1px solid ${BORDER}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <span style={{
              fontFamily: "var(--font-orbitron), 'Orbitron', sans-serif",
              fontSize: 10,
              letterSpacing: '0.15em',
              color: 'rgba(255,255,255,0.6)',
            }}>TWEAKS</span>
            <button
              onClick={() => setTweaksOpen(false)}
              style={{
                background: 'none',
                border: 'none',
                color: 'rgba(255,255,255,0.4)',
                cursor: 'pointer',
                fontSize: 14,
                lineHeight: 1,
                padding: 2,
              }}
            >✕</button>
          </div>
          {/* Inputs */}
          <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {(['car1Name', 'car2Name'] as const).map(key => (
              <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: 9,
                  letterSpacing: '0.15em',
                  textTransform: 'uppercase' as const,
                  color: 'rgba(255,255,255,0.3)',
                }}>
                  {key === 'car1Name' ? 'CAR 1 NAME' : 'CAR 2 NAME'}
                </label>
                <input
                  value={tweaks[key]}
                  onChange={e => setTweaks(prev => ({ ...prev, [key]: e.target.value }))}
                  style={{
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 3,
                    padding: '6px 10px',
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: 12,
                    color: '#fff',
                    outline: 'none',
                    width: '100%',
                    boxSizing: 'border-box' as const,
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tweaks toggle button */}
      <button
        onClick={() => setTweaksOpen(o => !o)}
        style={{
          position: 'fixed',
          bottom: 20,
          right: tweaksOpen ? 300 : 20,
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
          transition: 'right 0.2s ease',
        }}
      >
        ⚙
      </button>
    </>
  );
}
