'use client';

import React from 'react';
import {
  Label, Dot, Divider,
  MQTTLog, DeviceHealth,
  BG, BORDER,
} from '../shared';
import { ActTitle, KV, card } from './common';

export function ActDebug() {
  return (
    <div style={{
      flex: 1,
      display: 'grid',
      gridTemplateColumns: '1fr 380px',
      gap: 14,
      padding: 14,
      minHeight: 0,
      background: BG,
      overflow: 'hidden',
    }}>
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

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflow: 'auto' }}>
        <Label>DEVICE HEALTH</Label>
        <DeviceHealth />

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
