import React from 'react';

interface ThrottleIndicatorProps {
  throttle: number; // 0 to 1
  wPressed: boolean;
}

const ThrottleIndicator: React.FC<ThrottleIndicatorProps> = ({
  throttle,
  wPressed,
}) => {
  const percentage = Math.round(throttle * 100);

  // Determine fill color based on throttle level
  const getGradient = (): string => {
    if (throttle < 0.33) return 'from-green-500 to-green-400';
    if (throttle < 0.66) return 'from-yellow-500 to-yellow-400';
    return 'from-red-500 to-red-400';
  };

  return (
    <div className="flex flex-col items-center gap-3" aria-label="Throttle indicator">
      <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">
        Throttle
      </h3>

      {/* Key indicator */}
      <div
        className={`flex h-8 w-8 items-center justify-center rounded-md text-xs font-bold transition-all duration-200 ${
          wPressed ? 'key-active' : 'key-inactive'
        }`}
        aria-label={`W key ${wPressed ? 'pressed' : 'not pressed'}`}
      >
        W
      </div>

      {/* Gauge container */}
      <div className="relative flex flex-col items-center">
        <div
          className="relative h-48 w-12 overflow-hidden rounded-lg border border-slate-600 bg-slate-800/80"
          role="meter"
          aria-valuenow={percentage}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Throttle at ${percentage} percent`}
        >
          {/* Background grid lines */}
          <div className="absolute inset-0 flex flex-col justify-between px-0.5 py-1 opacity-20">
            {Array.from({ length: 11 }).map((_, i) => (
              <div key={i} className="h-px w-full bg-slate-400" />
            ))}
          </div>

          {/* Fill */}
          <div
            className={`gauge-fill absolute bottom-0 left-0 right-0 rounded-b-md bg-gradient-to-t ${getGradient()}`}
            style={{ height: `${percentage}%` }}
          >
            {/* Shimmer effect */}
            <div className="absolute inset-0 bg-gradient-to-t from-transparent via-white/10 to-transparent" />
          </div>
        </div>

        {/* Scale labels */}
        <div className="absolute -right-7 top-0 flex h-48 flex-col justify-between text-[10px] text-slate-500">
          <span>100</span>
          <span>50</span>
          <span>0</span>
        </div>
      </div>

      {/* Percentage text */}
      <span
        className="font-mono text-2xl font-bold text-white"
        aria-hidden="true"
      >
        {percentage}%
      </span>
    </div>
  );
};

export default ThrottleIndicator;
