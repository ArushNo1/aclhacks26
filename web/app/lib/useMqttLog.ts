'use client';

// Rolling tail of /ws/mqtt records (Act 4 DEBUG). Reconnects with backoff
// independently of the telemetry stream so MQTT outages don't kill the
// race feed.

import { useEffect, useRef, useState } from 'react';

export interface MqttRecord {
  ts: number;
  topic: string;
  payload: string;
  size: number;
}

const MAX = 200;

function wsUrl(): string {
  if (typeof window === 'undefined') return '';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws/mqtt`;
}

export function useMqttLog(): MqttRecord[] {
  const [records, setRecords] = useState<MqttRecord[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let delay = 250;

    const connect = () => {
      if (cancelled) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(wsUrl());
      } catch {
        setTimeout(connect, delay);
        delay = Math.min(delay * 2, 5000);
        return;
      }
      wsRef.current = ws;
      ws.onopen = () => { delay = 250; };
      ws.onmessage = (ev) => {
        try {
          const r = JSON.parse(ev.data) as MqttRecord;
          if (!r.topic) return; // skip handshake/error envelopes
          setRecords(prev => {
            const next = prev.length >= MAX ? prev.slice(prev.length - MAX + 1) : prev.slice();
            next.push(r);
            return next;
          });
        } catch {
          // ignore
        }
      };
      ws.onclose = () => {
        if (cancelled) return;
        setTimeout(connect, delay);
        delay = Math.min(delay * 2, 5000);
      };
      ws.onerror = () => { try { ws.close(); } catch { /* noop */ } };
    };

    connect();
    return () => {
      cancelled = true;
      try { wsRef.current?.close(); } catch { /* noop */ }
    };
  }, []);

  return records;
}
