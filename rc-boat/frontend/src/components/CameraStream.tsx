/**
 * CameraStream — Live FPV video display.
 *
 * Displays the MJPEG stream from the Raspberry Pi camera.
 * Uses a plain <img> element which natively supports multipart/x-mixed-replace
 * streams in all modern browsers — no JS video decoding needed.
 *
 * Features:
 *  - Loading / error / streaming / disabled states
 *  - FPS counter (measured from img onLoad events)
 *  - Resolution display
 *  - Fullscreen support (Fullscreen API)
 *  - Camera enable/disable toggle
 *  - Manual reconnect button
 *  - Auto-reconnect on error
 *  - FPV HUD corner brackets when streaming
 */
import React, { useRef, useCallback, useEffect } from 'react';
import { CameraStreamControls, CameraStatus } from '../hooks/useCameraStream';

interface CameraStreamProps {
  controls: CameraStreamControls;
}

const STATUS_LABELS: Record<CameraStatus, string> = {
  disabled: 'Camera Disabled',
  connecting: 'Connecting…',
  streaming: 'Streaming',
  error: 'Stream Error',
  offline: 'Camera Offline',
};

const STATUS_COLORS: Record<CameraStatus, string> = {
  disabled: 'text-slate-400',
  connecting: 'text-yellow-400',
  streaming: 'text-green-400',
  error: 'text-red-400',
  offline: 'text-red-400',
};

const STATUS_DOT_COLORS: Record<CameraStatus, string> = {
  disabled: 'bg-slate-500',
  connecting: 'bg-yellow-400 animate-pulse-dot',
  streaming: 'bg-green-400 animate-pulse-dot',
  error: 'bg-red-400',
  offline: 'bg-red-400',
};

const CameraStream: React.FC<CameraStreamProps> = ({ controls }) => {
  const { state, enable, disable, reconnect, recordFrame } = controls;
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const errorRetryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Fullscreen ────────────────────────────────────────────────────────────
  const toggleFullscreen = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      void el.requestFullscreen();
    } else {
      void document.exitFullscreen();
    }
  }, []);

  // ── Img event handlers ────────────────────────────────────────────────────
  const handleLoad = useCallback(() => {
    recordFrame();
    // Clear any pending error retry
    if (errorRetryRef.current) {
      clearTimeout(errorRetryRef.current);
      errorRetryRef.current = null;
    }
  }, [recordFrame]);

  const handleError = useCallback(() => {
    if (!state.enabled) return;
    // Auto-retry after 3s
    if (errorRetryRef.current) clearTimeout(errorRetryRef.current);
    errorRetryRef.current = setTimeout(() => {
      reconnect();
    }, 3000);
  }, [state.enabled, reconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (errorRetryRef.current) clearTimeout(errorRetryRef.current);
    };
  }, []);

  const showVideo =
    state.enabled && (state.status === 'streaming' || state.status === 'connecting');

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/60 shadow-lg shadow-black/20 overflow-hidden">
      {/* ── Header bar ────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700/60">
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold uppercase tracking-widest text-slate-400">
            📷 Live Camera Feed
          </span>
          {/* Status badge */}
          <div className="flex items-center gap-1.5">
            <span
              className={`inline-block h-2 w-2 rounded-full ${STATUS_DOT_COLORS[state.status]}`}
              aria-hidden="true"
            />
            <span className={`text-xs font-medium ${STATUS_COLORS[state.status]}`}>
              {STATUS_LABELS[state.status]}
            </span>
          </div>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-2">
          {/* FPS */}
          {state.status === 'streaming' && (
            <span className="font-mono text-xs text-slate-400 tabular-nums">
              {state.fps} fps
            </span>
          )}

          {/* Resolution */}
          {state.resolution && (
            <span className="font-mono text-xs text-slate-500 tabular-nums">
              {state.resolution.width}×{state.resolution.height}
            </span>
          )}

          {/* Reconnect button — shown when enabled but not streaming */}
          {state.enabled && state.status !== 'streaming' && (
            <button
              onClick={reconnect}
              className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-slate-600 transition-colors"
              aria-label="Reconnect camera"
            >
              ↺ Reconnect
            </button>
          )}

          {/* Fullscreen button */}
          <button
            onClick={toggleFullscreen}
            className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-slate-600 transition-colors"
            aria-label="Toggle fullscreen"
            title="Fullscreen"
          >
            ⛶
          </button>

          {/* Enable/disable toggle */}
          <button
            onClick={state.enabled ? disable : enable}
            className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
              state.enabled
                ? 'bg-blue-600/30 text-blue-400 hover:bg-blue-600/50'
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
            }`}
            aria-label={state.enabled ? 'Disable camera' : 'Enable camera'}
          >
            {state.enabled ? '🎥 On' : '🚫 Off'}
          </button>
        </div>
      </div>

      {/* ── Video area ────────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        className="relative w-full bg-slate-950"
        style={{ aspectRatio: '16/9', minHeight: '200px' }}
      >
        {/* Live img stream — browser natively handles multipart/x-mixed-replace */}
        {showVideo && (
          <img
            ref={imgRef}
            src={state.streamUrl}
            alt="Live FPV camera feed"
            onLoad={handleLoad}
            onError={handleError}
            className="absolute inset-0 h-full w-full object-contain"
            style={{ imageRendering: 'auto' }}
          />
        )}

        {/* Overlay states when video is not shown */}
        {!showVideo && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
            {state.status === 'disabled' && (
              <>
                <span className="text-4xl opacity-40" aria-hidden="true">
                  📷
                </span>
                <p className="text-sm text-slate-500">Camera disabled</p>
                <button
                  onClick={enable}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
                >
                  Enable Camera
                </button>
              </>
            )}

            {(state.status === 'error' || state.status === 'offline') && (
              <>
                <span className="text-4xl opacity-50" aria-hidden="true">
                  📡
                </span>
                <p className="text-sm font-medium text-red-400">
                  {state.errorMessage ?? 'Stream unavailable'}
                </p>
                <p className="text-xs text-slate-500">Retrying automatically…</p>
                <button
                  onClick={reconnect}
                  className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-600 transition-colors"
                >
                  ↺ Reconnect Now
                </button>
              </>
            )}

            {state.status === 'connecting' && (
              <>
                <svg
                  className="h-8 w-8 animate-spin text-blue-400"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                <p className="text-sm text-slate-400">Connecting to camera…</p>
              </>
            )}
          </div>
        )}

        {/* FPV HUD corner brackets — visible only when streaming */}
        {state.status === 'streaming' && (
          <>
            {/* Top-left */}
            <div className="absolute top-2 left-2 h-5 w-5 border-t-2 border-l-2 border-green-400/60 pointer-events-none" />
            {/* Top-right */}
            <div className="absolute top-2 right-2 h-5 w-5 border-t-2 border-r-2 border-green-400/60 pointer-events-none" />
            {/* Bottom-left */}
            <div className="absolute bottom-2 left-2 h-5 w-5 border-b-2 border-l-2 border-green-400/60 pointer-events-none" />
            {/* Bottom-right */}
            <div className="absolute bottom-2 right-2 h-5 w-5 border-b-2 border-r-2 border-green-400/60 pointer-events-none" />
          </>
        )}
      </div>
    </div>
  );
};

export default CameraStream;
