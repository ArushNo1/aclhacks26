// Lightweight typed wrappers around the Python server REST surface.
// All paths are relative — the Next dev rewrites in next.config.ts proxy them
// to the uvicorn server on localhost:8000.

export type Phase = 'idle' | 'capture' | 'training' | 'race';
export type LightPhase = 'off' | 'red' | 'yellow' | 'green';

export interface CarSnapshot {
  position_on_track: number;
  lap_count: number;
  lap_times: number[];
  last_lap_s: number | null;
  best_lap_s: number | null;
  speed: number;
}

export interface RaceSnapshot {
  light_phase: LightPhase;
  started: boolean;
  race_clock: number;
  off_track: boolean;
  collision: boolean;
  car1: CarSnapshot;
  car2: CarSnapshot;
}

export interface HandCalibrationStep {
  index: number;        // 1-based
  total: number;
  target: 'L' | 'R';
  anchor: 'neutral' | 'forward' | 'backward';
  prompt: string;
}

export interface HandCalibrationStatus {
  active: boolean;
  completed: boolean;
  error: string | null;
  last_captured_size: number | null;
  step: HandCalibrationStep | null;
}

export interface HandProfile {
  left_neutral_size: number;
  left_forward_size: number;
  left_backward_size: number;
  right_neutral_size: number;
  right_forward_size: number;
  right_backward_size: number;
}

export interface HandSnapshot {
  has_left: boolean;
  has_right: boolean;
  steer: number;
  throttle: number;
  raw_left_size: number;
  raw_right_size: number;
  attached: boolean;
  calibrated: boolean;
  profile: HandProfile | null;
  calibration: HandCalibrationStatus;
}

export interface TrainingSnapshot {
  running: boolean;
  current_epoch: number;
  total_epochs: number;
  current_loss: number;
  loss_points: number[];
  last_status: string;
  policy_version: string | null;
}

export interface CaptureSnapshot {
  recording: boolean;
  session_id: string | null;
  started_at: number | null;
  duration_s: number;
  frames: number;
  last_save_path: string | null;
}

export interface SimSnapshot {
  ts: number;
  tick: number;
  phase: Phase;
  fps: number;
  policy_active: 'none' | 'bc' | 'rl' | 'human';
  policy_version: string | null;
  race: RaceSnapshot;
  hand: HandSnapshot;
  training: TrainingSnapshot;
  capture: CaptureSnapshot;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${path} -> HTTP ${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  status: () => jsonFetch<SimSnapshot>('/api/status'),
  raceStart: () => jsonFetch<{ started: boolean }>('/api/race/start', { method: 'POST' }),
  raceReset: () => jsonFetch<{ reset: boolean }>('/api/race/reset', { method: 'POST' }),
  setPolicy: (name: 'none' | 'bc' | 'rl') =>
    jsonFetch<{ policy_active: string }>(
      '/api/policy/active',
      { method: 'POST', body: JSON.stringify({ name }) }
    ),
  reloadPolicy: () => jsonFetch<{ policy_version: string }>('/api/policy/reload', { method: 'POST' }),
  leaderboard: () =>
    jsonFetch<{ rows: { name: string; laps: number; best_lap_s: number | null; last_lap_s: number | null }[] }>(
      '/api/leaderboard'
    ),
  health: () =>
    jsonFetch<{ devices: { name: string; sub: string; metrics: Record<string, string> }[] }>(
      '/api/health'
    ),
  captureStart: () =>
    jsonFetch<{ session_id: string; started_at: number }>('/api/capture/start', { method: 'POST' }),
  captureStop: () =>
    jsonFetch<{ session_id: string | null; frames: number; path: string }>('/api/capture/stop', { method: 'POST' }),
  trainStart: (epochs?: number) =>
    jsonFetch<{ started: boolean; epochs: number }>(
      '/api/train/start',
      { method: 'POST', body: JSON.stringify({ epochs }) }
    ),
  trainStop: () => jsonFetch<{ running: boolean }>('/api/train/stop', { method: 'POST' }),
  // ---- hand calibration (Act 1) ----
  handStatus: () =>
    jsonFetch<{ attached: boolean; error: string | null; calibrated: boolean; calibration: HandCalibrationStatus | null }>(
      '/api/hand/status'
    ),
  handCalibrateStart: () =>
    jsonFetch<HandCalibrationStatus>('/api/hand/calibrate/start', { method: 'POST' }),
  handCalibrateCapture: () =>
    jsonFetch<HandCalibrationStatus>('/api/hand/calibrate/capture', { method: 'POST' }),
  handCalibrateRedo: () =>
    jsonFetch<HandCalibrationStatus>('/api/hand/calibrate/redo', { method: 'POST' }),
  handCalibrateCancel: () =>
    jsonFetch<HandCalibrationStatus>('/api/hand/calibrate/cancel', { method: 'POST' }),
  handReset: () =>
    jsonFetch<HandCalibrationStatus>('/api/hand/reset', { method: 'POST' }),
  setPovSource: (source: 'sim' | 'car', carId: string = '1') =>
    jsonFetch<{ source: string; car_id: string | null }>(
      '/api/pov/source',
      { method: 'POST', body: JSON.stringify({ source, car_id: carId }) }
    ),
};
