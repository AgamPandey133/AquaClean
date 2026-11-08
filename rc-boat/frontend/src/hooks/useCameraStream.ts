/**
 * useCameraStream — manages MJPEG camera stream state.
 *
 * Polls /camera/status every 2s to get server-side camera info
 * (resolution, FPS, active clients). The actual video is loaded
 * directly by the CameraStream component via an <img> src pointing
 * at the MJPEG endpoint — the browser handles the multipart stream.
 *
 * This hook only manages:
 *   - Whether camera is enabled (user toggle)
 *   - Camera server status (online/offline)
 *   - FPS measurement from img load events
 *   - Reconnect logic
 */
import { useState, useEffect, useRef, useCallback } from 'react';

export type CameraStatus = 'disabled' | 'connecting' | 'streaming' | 'error' | 'offline';

export interface CameraStreamState {
  status: CameraStatus;
  enabled: boolean;
  fps: number;
  resolution: { width: number; height: number } | null;
  activeClients: number;
  errorMessage: string | null;
  streamUrl: string;
}

export interface CameraStreamControls {
  state: CameraStreamState;
  enable: () => void;
  disable: () => void;
  reconnect: () => void;
  recordFrame: () => void;
}

const STATUS_POLL_MS = 2000;
const FPS_WINDOW_MS = 2000;

export function useCameraStream(): CameraStreamControls {
  const cameraUrl = import.meta.env.VITE_CAMERA_URL || 'http://localhost:8000/video';
  const statusUrl = import.meta.env.VITE_CAMERA_STATUS_URL || 'http://localhost:8000/camera/status';

  const [state, setState] = useState<CameraStreamState>({
    status: 'connecting',
    enabled: true,
    fps: 0,
    resolution: null,
    activeClients: 0,
    errorMessage: null,
    streamUrl: cameraUrl,
  });

  const mountedRef = useRef(true);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const frameTimesRef = useRef<number[]>([]);
  const reconnectKeyRef = useRef(0);
  const enabledRef = useRef(true);

  // ── FPS measurement — called by CameraStream on each img load ─────────────
  const recordFrame = useCallback(() => {
    const now = performance.now();
    frameTimesRef.current.push(now);
    const cutoff = now - FPS_WINDOW_MS;
    frameTimesRef.current = frameTimesRef.current.filter((t) => t >= cutoff);
    const fps = Math.round((frameTimesRef.current.length / FPS_WINDOW_MS) * 1000);
    setState((prev) => ({ ...prev, fps, status: 'streaming' }));
  }, []);

  // ── Status polling ────────────────────────────────────────────────────────
  const pollStatus = useCallback(async () => {
    if (!mountedRef.current || !enabledRef.current) return;
    try {
      const res = await fetch(statusUrl, { signal: AbortSignal.timeout(1500) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as {
        running: boolean;
        resolution?: { width: number; height: number };
        active_clients?: number;
      };
      if (!mountedRef.current) return;
      setState((prev) => ({
        ...prev,
        resolution: data.resolution ?? null,
        activeClients: data.active_clients ?? 0,
        errorMessage: data.running ? null : prev.errorMessage,
      }));
    } catch {
      if (!mountedRef.current) return;
      setState((prev) =>
        prev.status !== 'streaming'
          ? { ...prev, status: 'offline', errorMessage: 'Cannot reach camera server' }
          : prev,
      );
    }
  }, [statusUrl]);

  // ── Enable / disable / reconnect ─────────────────────────────────────────
  const enable = useCallback(() => {
    enabledRef.current = true;
    setState((prev) => ({ ...prev, enabled: true, status: 'connecting', errorMessage: null }));
  }, []);

  const disable = useCallback(() => {
    enabledRef.current = false;
    frameTimesRef.current = [];
    setState((prev) => ({ ...prev, enabled: false, status: 'disabled', fps: 0 }));
  }, []);

  const reconnect = useCallback(() => {
    reconnectKeyRef.current += 1;
    const newUrl = `${cameraUrl}?r=${reconnectKeyRef.current}`;
    frameTimesRef.current = [];
    setState((prev) => ({
      ...prev,
      status: 'connecting',
      errorMessage: null,
      fps: 0,
      streamUrl: newUrl,
    }));
    void pollStatus();
  }, [cameraUrl, pollStatus]);

  // ── Polling lifecycle ─────────────────────────────────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    enabledRef.current = state.enabled;

    if (state.enabled) {
      void pollStatus();
      pollTimerRef.current = setInterval(() => {
        void pollStatus();
      }, STATUS_POLL_MS);
    }

    return () => {
      mountedRef.current = false;
      if (pollTimerRef.current !== null) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.enabled]);

  return { state, enable, disable, reconnect, recordFrame };
}
