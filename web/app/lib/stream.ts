// Single shared subscription to /ws/telemetry. Reconnects with exponential
// backoff up to ~5 s. Components subscribe via useStream(selector).

import type { SimSnapshot } from './api';

type Listener = () => void;

let snapshot: SimSnapshot | null = null;
const listeners = new Set<Listener>();
let ws: WebSocket | null = null;
let reconnectDelayMs = 250;
let openCount = 0;
let closeCount = 0;

function wsUrl(path: string): string {
  if (typeof window === 'undefined') return '';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}`;
}

function notify(): void {
  for (const l of listeners) l();
}

function connect(): void {
  if (typeof window === 'undefined') return;
  try {
    ws = new WebSocket(wsUrl('/ws/telemetry'));
  } catch {
    setTimeout(connect, reconnectDelayMs);
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, 5000);
    return;
  }
  ws.onopen = () => {
    openCount += 1;
    reconnectDelayMs = 250;
  };
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data) as SimSnapshot;
      snapshot = data;
      notify();
    } catch {
      // ignore malformed frames
    }
  };
  ws.onclose = () => {
    closeCount += 1;
    ws = null;
    setTimeout(connect, reconnectDelayMs);
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, 5000);
  };
  ws.onerror = () => {
    // onclose will fire next, which handles reconnect
    try { ws?.close(); } catch { /* noop */ }
  };
}

let started = false;
function ensureStarted(): void {
  if (started || typeof window === 'undefined') return;
  started = true;
  connect();
}

export function getSnapshot(): SimSnapshot | null {
  return snapshot;
}

export function subscribe(listener: Listener): () => void {
  ensureStarted();
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function streamStats() {
  return { openCount, closeCount, listeners: listeners.size };
}
