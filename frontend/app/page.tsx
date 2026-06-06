"use client";
export const dynamic = "force-dynamic";
import React, { useState, useEffect } from 'react';
import NHLMatchupCard from '../components/NHLMatchupCard';
import PerformanceTracker from '../components/PerformanceTracker';

const TopPlaysList = () => {
  const [plays, setPlays] = useState(null);
  useEffect(() => {
    fetch('/daily_predictions.json?t=' + new Date().getTime())
      .then(res => res.json())
      .then(json => setPlays(json.top_plays || []))
      .catch(err => console.error(err));
  }, []);

  if (!plays) return (
    <div className="flex justify-center mt-20">
      <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  );
  if (plays.length === 0) return (
    <div className="text-center text-gray-500 mt-20 font-mono text-sm px-4">
      No EDGE or BIG plays found today. Check tomorrow's slate.
    </div>
  );
  return (
    <div className="space-y-4 max-w-3xl mx-auto px-2">
      <h2 className="text-xl font-bold text-gray-100 uppercase tracking-wide mb-6 text-center">Top Engine Plays</h2>
      {plays.map((game, idx) => (
        <div key={idx} className="bg-[#151c28] border border-gray-800 rounded-xl p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 shadow-lg hover:border-gray-600 transition-colors">
          <div className="flex items-center space-x-4">
            <div className="text-3xl font-black italic text-[#1f2937]">#{idx + 1}</div>
            <div>
              <h3 className="text-base sm:text-xl font-black text-white">{game.away.name} @ {game.home.name}</h3>
              <p className="text-xs text-gray-400 mt-1">Win Prob: <span className="text-emerald-400 font-bold">{game.prob}</span></p>
            </div>
          </div>
          <div className="text-left sm:text-right pl-14 sm:pl-0">
            <div className="text-emerald-400 font-black text-base sm:text-xl">{game.details.best_angle.play}</div>
            <div className="text-xs text-gray-500 mt-1">
              Edge: <span className="text-emerald-500 font-bold">{game.edge}</span> · Tier: <span className="text-white font-bold">{game.tier}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ── Always use Eastern Time (EDT) for NHL game dates ──────────────────────────
// Reliably extracts the EDT calendar date using Intl API (works in any timezone)
const getESTDate = (offsetDays = 0) => {
  const now = new Date();
  // Extract EDT date parts — reliable across all timezones (IST, PST, GMT, etc.)
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric", month: "2-digit", day: "2-digit"
  }).formatToParts(now);
  const year  = parseInt(parts.find(p => p.type === "year").value);
  const month = parseInt(parts.find(p => p.type === "month").value) - 1;
  const day   = parseInt(parts.find(p => p.type === "day").value);
  // Build UTC date from EDT parts and apply offset
  return new Date(Date.UTC(year, month, day + offsetDays));
};

// Format using UTC methods to avoid local timezone interference
const fmtDate = (d) => {
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return months[d.getUTCMonth()] + " " + d.getUTCDate();
};

const buildDateOptions = () => {
  const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  return [
    { key: 'day_before_yesterday', label: fmtDate(getESTDate(-2)), sub: '2 Days Ago' },
    { key: 'yesterday',            label: fmtDate(getESTDate(-1)), sub: 'Yesterday'  },
    { key: 'today',                label: fmtDate(getESTDate( 0)), sub: 'Today'      },
    { key: 'tomorrow',             label: fmtDate(getESTDate( 1)), sub: 'Tomorrow'   },
    { key: 'day_after_tomorrow',   label: fmtDate(getESTDate( 2)), sub: days[getESTDate(2).getUTCDay()] },
  ];
};

export default function NHLDashboard() {
  const [activeMode, setActiveMode] = useState('daily');
  const [activeDate, setActiveDate] = useState('today');
  const dateOptions = buildDateOptions();

  return (
    <div className="min-h-screen bg-[#0b0f19] text-gray-100 font-sans">
      {/* HEADER */}
      <div className="sticky top-0 z-50 bg-[#0b0f19]/95 backdrop-blur border-b border-gray-800">
        <div className="max-w-5xl mx-auto px-3 sm:px-6 py-3 flex items-center justify-between gap-2">
          <h1 className="text-lg sm:text-3xl font-black italic tracking-wider text-white whitespace-nowrap">
            SUMEET<span className="text-blue-500">ENGINE</span> <span className="text-gray-500 text-sm sm:text-lg">NHL</span>
          </h1>
          <div className="flex space-x-1 bg-[#111827] p-1 rounded-lg border border-gray-800">
            {['daily','snapshot','top'].map((mode) => (
              <button
                key={mode}
                onClick={() => setActiveMode(mode)}
                className={`px-2 sm:px-4 py-1.5 rounded-md text-[10px] sm:text-sm font-bold uppercase tracking-wide transition-all ${
                  activeMode === mode ? 'bg-blue-600 text-white shadow-md' : 'text-gray-400 hover:text-white'
                }`}
              >
                {mode === 'top' ? 'Top' : mode === 'snapshot' ? 'Snap' : mode}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-4">

        {/* DATE SELECTOR */}
        {activeMode === 'daily' && (
          <div className="overflow-x-auto pb-1 -mx-3 px-3">
            <div className="flex space-x-2 min-w-max mx-auto w-fit">
              {dateOptions.map(({ key, label, sub }) => (
                <button
                  key={key}
                  onClick={() => setActiveDate(key)}
                  className={`flex flex-col items-center px-3 sm:px-5 py-2 sm:py-3 rounded-xl border transition-all ${
                    activeDate === key
                      ? 'bg-blue-600 border-blue-500 text-white shadow-lg'
                      : 'bg-[#111827] border-gray-800 text-gray-400 hover:border-gray-600 hover:text-gray-200'
                  }`}
                >
                  <span className="text-[9px] sm:text-[10px] uppercase tracking-widest font-bold opacity-70">{sub}</span>
                  <span className="text-sm sm:text-base font-black mt-0.5">{label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* CONTENT */}
        <div className="mt-2">
          {activeMode === 'snapshot' && <PerformanceTracker />}
          {activeMode === 'daily'    && <NHLMatchupCard dateMode={activeDate} />}
          {activeMode === 'top'      && <TopPlaysList />}
        </div>

      </div>
    </div>
  );
}