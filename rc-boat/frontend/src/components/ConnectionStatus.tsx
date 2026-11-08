import React from 'react';

interface ConnectionStatusProps {
  connected: boolean;
  simulation: boolean;
  armed: boolean;
  emergencyStopped: boolean;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  connected,
  simulation,
  armed,
  emergencyStopped,
}) => {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Connection indicator */}
      <div
        className="flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium"
        role="status"
        aria-live="polite"
        aria-label={connected ? 'Connected to boat' : 'Disconnected from boat'}
      >
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full animate-pulse-dot ${
            connected ? 'bg-green-500 shadow-green-500/50 shadow-lg' : 'bg-red-500 shadow-red-500/50 shadow-lg'
          }`}
          aria-hidden="true"
        />
        <span className={connected ? 'text-green-400' : 'text-red-400'}>
          {connected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {/* Disconnected warning */}
      {!connected && (
        <span className="text-xs text-red-400/80">
          Attempting to reconnect…
        </span>
      )}

      {/* Simulation badge */}
      {simulation && (
        <span
          className="rounded-full bg-purple-500/20 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-purple-400 ring-1 ring-purple-500/40"
          role="status"
          aria-label="Simulation mode active"
        >
          Simulation Mode
        </span>
      )}

      {/* Armed / Disarmed badge */}
      <span
        className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider ring-1 ${
          armed
            ? 'bg-green-500/20 text-green-400 ring-green-500/40'
            : 'bg-slate-600/30 text-slate-400 ring-slate-500/40'
        }`}
        role="status"
        aria-label={armed ? 'Boat is armed' : 'Boat is disarmed'}
      >
        {armed ? 'Armed' : 'Disarmed'}
      </span>

      {/* Emergency stopped badge */}
      {emergencyStopped && (
        <span
          className="rounded-full bg-red-500/20 px-3 py-1 text-xs font-bold uppercase tracking-wider text-red-400 ring-1 ring-red-500/40"
          role="alert"
          aria-label="Emergency stopped"
        >
          ⚠ Emergency Stopped
        </span>
      )}
    </div>
  );
};

export default ConnectionStatus;
