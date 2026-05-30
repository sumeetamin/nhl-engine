import React, { useState, useEffect } from 'react';

/**
 * PerformanceTracker — Snapshot Tab
 *
 * Reads from /historical_stats.json
 * Expected structure for historical_stats.json:
 * {
 *   "all_time":   { "ml": {...}, "spread": {...}, "ou": {...}, "edge": {...}, "overall": {...} },
 *   "this_month": { "ml": {...}, "spread": {...}, "ou": {...}, "edge": {...}, "overall": {...} },
 *   "this_week":  { "ml": {...}, "spread": {...}, "ou": {...}, "edge": {...}, "overall": {...} },
 *   "yesterday":  { "ml": {...}, "spread": {...}, "ou": {...}, "edge": {...}, "overall": {...} }
 * }
 * Each sub-object: { "wins": 25, "losses": 18, "pushes": 2, "win_rate": "58.1%", "avg_edge": "+9.2%", "units": "+12.4" }
 */

const PERIODS = [
  { key: 'all_time',   label: 'All Time'  },
  { key: 'this_month', label: 'Month'     },
  { key: 'this_week',  label: 'Week'      },
  { key: 'yesterday',  label: 'Yesterday' },
];

const PLAY_TYPES = [
  { key: 'ml',     label: 'Moneyline',  abbr: 'ML',     color: 'emerald', icon: '💰' },
  { key: 'spread', label: 'Spread',     abbr: 'ATS',    color: 'blue',    icon: '📊' },
  { key: 'ou',     label: 'Over/Under', abbr: 'O/U',    color: 'violet',  icon: '🎯' },
  { key: 'edge',   label: 'Edge Plays', abbr: 'EDGE',   color: 'amber',   icon: '⚡' },
];

const colorMap = {
  emerald: { bg: 'bg-emerald-900/20', border: 'border-emerald-800/40', text: 'text-emerald-400', badge: 'bg-emerald-900/40 text-emerald-300', bar: 'bg-emerald-500' },
  blue:    { bg: 'bg-blue-900/20',    border: 'border-blue-800/40',    text: 'text-blue-400',    badge: 'bg-blue-900/40 text-blue-300',    bar: 'bg-blue-500'    },
  violet:  { bg: 'bg-violet-900/20',  border: 'border-violet-800/40',  text: 'text-violet-400',  badge: 'bg-violet-900/40 text-violet-300', bar: 'bg-violet-500'  },
  amber:   { bg: 'bg-amber-900/20',   border: 'border-amber-800/40',   text: 'text-amber-400',   badge: 'bg-amber-900/40 text-amber-300',   bar: 'bg-amber-500'   },
};

// Win rate bar width (clamp between 0-100)
const toBarWidth = (rate) => {
  if (!rate) return 0;
  const n = parseFloat(rate);
  return isNaN(n) ? 0 : Math.max(0, Math.min(100, n));
};

const StatCard = ({ type, data }) => {
  const c = colorMap[type.color];
  const wins   = data?.wins   ?? '—';
  const losses = data?.losses ?? '—';
  const pushes = data?.pushes;
  const rate   = data?.win_rate ?? null;
  const edge   = data?.avg_edge ?? null;
  const units  = data?.units ?? null;
  const barW   = toBarWidth(rate);

  const rateColor = barW >= 55 ? c.text : barW >= 50 ? 'text-gray-300' : 'text-red-400';

  return (
    <div className={`${c.bg} border ${c.border} rounded-xl p-4 sm:p-5 flex flex-col space-y-3`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-base">{type.icon}</span>
          <div>
            <p className="text-[10px] uppercase tracking-widest text-gray-500 font-bold">{type.label}</p>
            <span className={`text-[9px] font-black uppercase px-1.5 py-0.5 rounded ${c.badge}`}>{type.abbr}</span>
          </div>
        </div>
        {rate && (
          <p className={`text-2xl font-black ${rateColor}`}>{rate}</p>
        )}
        {!rate && (
          <p className="text-xl font-black text-gray-600">—</p>
        )}
      </div>

      {/* Win/Loss */}
      <div className="flex items-center space-x-3 font-mono">
        <span className="text-emerald-400 font-black text-lg">{wins}W</span>
        <span className="text-gray-700">·</span>
        <span className="text-red-400 font-black text-lg">{losses}L</span>
        {pushes !== undefined && pushes > 0 && (
          <>
            <span className="text-gray-700">·</span>
            <span className="text-gray-500 font-bold text-sm">{pushes}P</span>
          </>
        )}
      </div>

      {/* Win rate bar */}
      {rate && (
        <div className="w-full bg-[#0b0f19] rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full ${c.bar} rounded-full transition-all duration-700`}
            style={{ width: `${barW}%` }}
          />
        </div>
      )}

      {/* Edge & Units */}
      <div className="flex items-center justify-between pt-1 border-t border-gray-800/60">
        {edge ? (
          <div>
            <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-0.5">Avg Edge</p>
            <p className={`text-xs font-black ${c.text}`}>{edge}</p>
          </div>
        ) : <div />}
        {units ? (
          <div className="text-right">
            <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-0.5">Units</p>
            <p className={`text-xs font-black ${parseFloat(units) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {parseFloat(units) >= 0 ? '+' : ''}{units}u
            </p>
          </div>
        ) : <div />}
      </div>

      {/* No data fallback */}
      {!rate && !wins && (
        <p className="text-[10px] text-gray-700 font-mono italic text-center pt-2">No data yet</p>
      )}
    </div>
  );
};

const PerformanceTracker = () => {
  const [period, setPeriod] = useState('all_time');
  const [historicalData, setHistoricalData] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const timestamp = new Date().getTime();
        const res = await fetch('/historical_stats.json?t=' + new Date().getTime())
        if (!res.ok) throw new Error('Not found');
        const hist = await res.json();
        setHistoricalData(hist);
        setLoading(false);
      } catch {
        setError(true);
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const periodData = historicalData?.[period] ?? null;
  const overall    = periodData?.overall ?? null;

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-5 font-sans">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-wider">
            Engine <span className="text-emerald-400">Snapshot</span>
          </h2>
          <p className="text-[10px] text-gray-600 uppercase tracking-widest mt-0.5 font-mono">Performance History · V5</p>
        </div>

        {/* Period tabs */}
        <div className="flex space-x-1 bg-[#111827] p-1 rounded-lg border border-gray-800 self-start sm:self-auto">
          {PERIODS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setPeriod(key)}
              className={`px-2.5 sm:px-4 py-1.5 rounded-md text-[10px] sm:text-xs font-bold uppercase tracking-wide transition-all ${
                period === key ? 'bg-blue-600 text-white shadow' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Overall summary bar */}
      {overall && (
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 flex flex-wrap gap-4 sm:gap-6 items-center">
          <div>
            <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-0.5">Overall Record</p>
            <p className="text-lg font-black font-mono">
              <span className="text-emerald-400">{overall.wins ?? '—'}W</span>
              <span className="text-gray-700 mx-1">·</span>
              <span className="text-red-400">{overall.losses ?? '—'}L</span>
            </p>
          </div>
          {overall.win_rate && (
            <div>
              <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-0.5">Win Rate</p>
              <p className="text-lg font-black text-white">{overall.win_rate}</p>
            </div>
          )}
          {overall.avg_edge && (
            <div>
              <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-0.5">Avg Edge</p>
              <p className="text-lg font-black text-emerald-400">{overall.avg_edge}</p>
            </div>
          )}
          {overall.units && (
            <div>
              <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-0.5">Total Units</p>
              <p className={`text-lg font-black ${parseFloat(overall.units) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {parseFloat(overall.units) >= 0 ? '+' : ''}{overall.units}u
              </p>
            </div>
          )}
          <div className="ml-auto">
            <span className="text-[9px] font-black uppercase px-2 py-1 rounded bg-emerald-900/30 text-emerald-400 border border-emerald-800/30">
              V5 Online
            </span>
          </div>
        </div>
      )}

      {/* No data state */}
      {error && (
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-6 text-center">
          <p className="text-gray-600 font-mono text-xs uppercase tracking-widest mb-2">historical_stats.json not found</p>
          <p className="text-gray-700 text-xs">Run the pipeline to generate performance history.</p>
        </div>
      )}

      {/* 4 play type cards */}
      {!error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
          {PLAY_TYPES.map((type) => (
            <StatCard
              key={type.key}
              type={type}
              data={periodData?.[type.key] ?? null}
            />
          ))}
        </div>
      )}

      {/* Footer note */}
      <p className="text-[9px] text-gray-700 font-mono text-center uppercase tracking-widest pt-2">
        Data updates daily · Engine V5 · Sumeet Analytics
      </p>
    </div>
  );
};

export default PerformanceTracker;
