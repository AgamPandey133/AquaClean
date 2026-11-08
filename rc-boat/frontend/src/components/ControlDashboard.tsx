import React from 'react';
import { useBoatControls } from '../hooks/useBoatControls';
import { useCameraStream } from '../hooks/useCameraStream';
import CameraStream from './CameraStream';
import ConnectionStatus from './ConnectionStatus';
import ThrottleIndicator from './ThrottleIndicator';
import SteeringIndicator from './SteeringIndicator';

const ControlDashboard: React.FC = () => {
  const { state, arm, disarm, emergencyStop } = useBoatControls();
  const cameraControls = useCameraStream();

  return (
    <div className="relative min-h-screen w-full bg-slate-950 p-4 md:p-8">
      <div className="mx-auto max-w-5xl space-y-6">

        {/* ── Header ────────────────────────────────────────────────────── */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/60 p-4 shadow-lg shadow-black/20 backdrop-blur-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h1 className="flex items-center gap-2 text-xl font-bold text-white md:text-2xl">
              <span aria-hidden="true">🚤</span>
              <span>RC Boat Control Center</span>
            </h1>
            <div className="flex flex-wrap items-center gap-4">
              <ConnectionStatus
                connected={state.connected}
                simulation={state.simulation}
                armed={state.armed}
                emergencyStopped={state.emergencyStopped}
              />
              {/* Camera status inline */}
              <div className="flex items-center gap-1.5 rounded-full px-3 py-1 bg-slate-700/40 text-xs">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    cameraControls.state.status === 'streaming'
                      ? 'bg-green-400 animate-pulse-dot'
                      : cameraControls.state.status === 'connecting'
                      ? 'bg-yellow-400 animate-pulse-dot'
                      : 'bg-slate-500'
                  }`}
                  aria-hidden="true"
                />
                <span className="text-slate-400">
                  Camera:{' '}
                  <span
                    className={
                      cameraControls.state.status === 'streaming'
                        ? 'text-green-400'
                        : cameraControls.state.status === 'connecting'
                        ? 'text-yellow-400'
                        : 'text-slate-500'
                    }
                  >
                    {cameraControls.state.status === 'streaming'
                      ? `${cameraControls.state.fps} fps`
                      : cameraControls.state.status === 'disabled'
                      ? 'Off'
                      : cameraControls.state.status === 'connecting'
                      ? 'Connecting…'
                      : 'Offline'}
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Live Camera Feed ───────────────────────────────────────────── */}
        <CameraStream controls={cameraControls} />

        {/* ── Gauges ────────────────────────────────────────────────────── */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/60 p-6 shadow-lg shadow-black/20 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-10 md:flex-row md:items-start md:justify-around">
            {/* Throttle */}
            <ThrottleIndicator
              throttle={state.throttle}
              wPressed={state.keysPressed.w}
            />

            {/* Divider */}
            <div className="hidden h-64 w-px bg-slate-700/60 md:block" />
            <div className="h-px w-full bg-slate-700/60 md:hidden" />

            {/* Steering */}
            <div className="w-full md:flex-1">
              <SteeringIndicator
                steering={state.steering}
                aPressed={state.keysPressed.a}
                dPressed={state.keysPressed.d}
              />
            </div>
          </div>
        </div>

        {/* ── Control Buttons ───────────────────────────────────────────── */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/60 p-4 shadow-lg shadow-black/20 backdrop-blur-sm">
          <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-center sm:gap-4">
            {/* Arm / Disarm */}
            {state.armed ? (
              <button
                onClick={disarm}
                className="rounded-lg bg-amber-600 px-6 py-3 text-sm font-bold uppercase tracking-wider text-white shadow-lg shadow-amber-600/25 transition-all duration-200 hover:bg-amber-500 hover:shadow-amber-500/30 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-slate-800 active:scale-95 disabled:opacity-50"
                disabled={!state.connected}
                aria-label="Disarm the boat"
              >
                🔓 Disarm
              </button>
            ) : (
              <button
                onClick={arm}
                className="rounded-lg bg-green-600 px-6 py-3 text-sm font-bold uppercase tracking-wider text-white shadow-lg shadow-green-600/25 transition-all duration-200 hover:bg-green-500 hover:shadow-green-500/30 focus:outline-none focus:ring-2 focus:ring-green-400 focus:ring-offset-2 focus:ring-offset-slate-800 active:scale-95 disabled:opacity-50"
                disabled={!state.connected}
                aria-label="Arm the boat"
              >
                🔒 Arm
              </button>
            )}

            {/* Emergency Stop */}
            <button
              onClick={emergencyStop}
              className="rounded-lg bg-red-600 px-8 py-4 text-base font-extrabold uppercase tracking-widest text-white shadow-lg shadow-red-600/30 ring-2 ring-red-500/50 transition-all duration-200 hover:bg-red-500 hover:shadow-red-500/40 hover:ring-red-400/60 focus:outline-none focus:ring-4 focus:ring-red-400 focus:ring-offset-2 focus:ring-offset-slate-800 active:scale-95"
              aria-label="Emergency stop"
            >
              ⛔ Emergency Stop
            </button>
          </div>
        </div>

        {/* ── Keyboard Instructions ─────────────────────────────────────── */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/60 p-4 shadow-lg shadow-black/20 backdrop-blur-sm">
          <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">
            Keyboard Controls
          </h2>
          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-5">
            <KbdHint label="Forward" keyName="W" />
            <KbdHint label="Left" keyName="A" />
            <KbdHint label="Right" keyName="D" />
            <KbdHint label="Stop" keyName="S" />
            <KbdHint label="E-Stop" keyName="Space" />
          </div>
        </div>

      </div>

      {/* ── Disconnected Overlay ──────────────────────────────────────── */}
      {!state.connected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm"
          role="alertdialog"
          aria-label="Connection lost"
        >
          <div className="mx-4 max-w-md rounded-2xl border border-red-500/30 bg-slate-900 p-8 text-center shadow-2xl shadow-red-500/10">
            <div className="mb-4 text-5xl" aria-hidden="true">
              📡
            </div>
            <h2 className="mb-2 text-xl font-bold text-red-400">
              Connection Lost
            </h2>
            <p className="text-sm text-slate-400">
              Unable to connect to the RC boat controller. The dashboard will
              automatically reconnect when the server is available.
            </p>
            <div className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-500">
              <svg
                className="h-4 w-4 animate-spin text-slate-500"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
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
              Reconnecting…
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Sub-component ────────────────────────────────────────────────────────────

interface KbdHintProps {
  label: string;
  keyName: string;
}

const KbdHint: React.FC<KbdHintProps> = ({ label, keyName }) => (
  <div className="flex items-center gap-2 rounded-lg bg-slate-700/40 px-3 py-2">
    <kbd className="rounded bg-slate-600 px-2 py-0.5 font-mono text-xs font-bold text-slate-200 shadow-sm">
      {keyName}
    </kbd>
    <span className="text-slate-400">{label}</span>
  </div>
);

export default ControlDashboard;
