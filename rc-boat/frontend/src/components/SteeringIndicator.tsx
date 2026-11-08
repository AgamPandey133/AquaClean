import React from 'react';

interface SteeringIndicatorProps {
  steering: number; // -1 (full left) to 1 (full right)
  aPressed: boolean;
  dPressed: boolean;
}

const SteeringIndicator: React.FC<SteeringIndicatorProps> = ({
  steering,
  aPressed,
  dPressed,
}) => {
  // Convert -1…1 to 0…100 for positioning
  const markerPosition = ((steering + 1) / 2) * 100;
  const angleDegrees = Math.round(Math.abs(steering) * 45);

  const getSteeringLabel = (): string => {
    if (Math.abs(steering) < 0.02) return 'Center';
    const direction = steering < 0 ? 'Left' : 'Right';
    return `${direction} ${angleDegrees}°`;
  };

  return (
    <div className="flex flex-col items-center gap-3" aria-label="Steering indicator">
      <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">
        Steering
      </h3>

      {/* Key indicators row */}
      <div className="flex items-center gap-6">
        <div
          className={`flex h-8 w-8 items-center justify-center rounded-md text-xs font-bold transition-all duration-200 ${
            aPressed ? 'key-active' : 'key-inactive'
          }`}
          aria-label={`A key ${aPressed ? 'pressed' : 'not pressed'}`}
        >
          A
        </div>

        <span className="text-xs text-slate-500">◄ LEFT — RIGHT ►</span>

        <div
          className={`flex h-8 w-8 items-center justify-center rounded-md text-xs font-bold transition-all duration-200 ${
            dPressed ? 'key-active' : 'key-inactive'
          }`}
          aria-label={`D key ${dPressed ? 'pressed' : 'not pressed'}`}
        >
          D
        </div>
      </div>

      {/* Gauge container */}
      <div className="w-full max-w-xs px-2">
        <div
          className="relative h-10 overflow-hidden rounded-lg border border-slate-600 bg-slate-800/80"
          role="meter"
          aria-valuenow={steering}
          aria-valuemin={-1}
          aria-valuemax={1}
          aria-label={`Steering: ${getSteeringLabel()}`}
        >
          {/* Left zone (for left turns) */}
          {steering < -0.02 && (
            <div
              className="gauge-fill absolute top-0 bottom-0 bg-blue-500/30"
              style={{
                left: `${markerPosition}%`,
                width: `${50 - markerPosition}%`,
              }}
            />
          )}

          {/* Right zone (for right turns) */}
          {steering > 0.02 && (
            <div
              className="gauge-fill absolute top-0 bottom-0 bg-blue-500/30"
              style={{
                left: '50%',
                width: `${markerPosition - 50}%`,
              }}
            />
          )}

          {/* Center line */}
          <div className="absolute left-1/2 top-0 h-full w-px -translate-x-px bg-slate-500/60" />

          {/* Tick marks */}
          <div className="absolute left-[25%] top-0 h-full w-px bg-slate-600/40" />
          <div className="absolute left-[75%] top-0 h-full w-px bg-slate-600/40" />

          {/* Marker */}
          <div
            className="steering-marker absolute top-1 bottom-1 w-1.5 -translate-x-1/2 rounded-full bg-blue-500 shadow-lg shadow-blue-500/50"
            style={{ left: `${markerPosition}%` }}
          />
        </div>

        {/* Scale labels */}
        <div className="mt-1.5 flex justify-between text-[10px] text-slate-500">
          <span>-1.0</span>
          <span>-0.5</span>
          <span>0.0</span>
          <span>0.5</span>
          <span>1.0</span>
        </div>
      </div>

      {/* Steering value text */}
      <span
        className="font-mono text-2xl font-bold text-white"
        aria-hidden="true"
      >
        {getSteeringLabel()}
      </span>
    </div>
  );
};

export default SteeringIndicator;
