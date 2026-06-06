"use client";
export const dynamic = 'force-dynamic'; // skip static pre-render — page uses live JSON data
import React, { useState, useEffect } from 'react';
import NHLMatchupCard from '../components/NHLMatchupCard';
import PerformanceTracker from '../components/PerformanceTracker';

// ─── Daily Edge Plays ─────────────────────────────────────────────────────────
// Shows ML / Spread / O/U edge boxes directly under the date toggle
const DailyEdgePlays = ({ dateMode }: { dateMode: string }) => {
  const [game, setGame] = useState<any>(null);

  useEffect(() => {
    fetch('/daily_predictions.json?t=' + new Date().getTime())
      .then(r => r.json())
      .then(json => setGame(json[dateMode] || null))
      .catch(console.error);
  }, [dateMode]);

  const covers = game?.details?.covers;
  const overallEdge = game?.edge;
  const tier = game?.tier;

  const edgeBoxes = [
    {
      label: 'ML Play',
      value: covers?.best_ml,
      accent: 'emerald',
      icon: '💰',
    },
    {
      label: 'Spread Play',
      value: covers?.best_spread,
      accent: 'blue',
      icon: '📊',
    },
    {
      label: 'O/U Play',
      value: covers?.best_ou,
      accent: 'violet',
      icon: '🎯',
    },
  ];

  const accentColors: Record<string, any> = {
    emerald: { border: 'border-emerald-900/50', text: 'text-emerald-400', pill: 'bg-emerald-900/30 text-emerald-400 border-emerald-800/40' },
    blue:    { border: 'border-blue-900/50',    text: 'text-blue-400',    pill: 'bg-blue-900/30 text-blue-400 border-blue-800/40' },
    violet:  { border: 'border-violet-900/50',  text: 'text-violet-400',  pill: 'bg-violet-900/30 text-violet-400 border-violet-800/40' },
  };

  return (
    <div className="mb-4">
      {/* Row header */}
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-[10px] uppercase tracking-widest text-gray-600 font-bold font-mono">Engine Edge Plays</span>
        {overallEdge && tier && (
          <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded border ${tier === 'BIG' ? 'bg-red-900/30 text-red-400 border-red-800/40' : 'bg-emerald-900/30 text-emerald-400 border-emerald-800/40'}`}>
            {tier} · {overallEdge}
          </span>
        )}
      </div>

      {/* 3 edge boxes */}
      <div className="grid grid-cols-3 gap-2 sm:gap-3">
        {edgeBoxes.map(({ label, value, accent, icon }) => {
          const c = accentColors[accent];
          return (
            <div
              key={label}
              className={`bg-[#111827] border ${c.border} rounded-xl p-2.5 sm:p-4 text-center transition-all hover:brightness-110`}
            >
              <p className="text-[9px] sm:text-[10px] uppercase tracking-widest text-gray-500 mb-1.5 font-bold">{label}</p>
              {value ? (
                <p className={`text-xs sm:text-base font-black ${c.text} leading-tight`}>{value}</p>
              ) : (
                <p className="text-[9px] sm:text-[10px] text-gray-700 font-mono italic mt-1">No Edge</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ─── Top Plays List ────────────────────────────────────────────────────────────
const TopPlaysList = () => {
  const [plays, setPlays] = useState<any[] | null>(null);

  useEffect(() => {
    fetch('/daily_predictions.json?t=' + new Date().getTime())
      .then(res => res.json())
      .then(json => setPlays(json.top_plays || []))
      .catch(err => console.error(err));
  }, []);

  if (!plays) {
     return (
       <div className="flex justify-center mt-20">
         <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
       </div>
     );
  }

  if (plays.length === 0) {
     return <div className="text-center text-gray-500 mt-20 font-mono">No EDGE or BIG plays found today. Check tomorrow's slate.</div>;
  }

  return (
    <div className="space-y-4 max-w-3xl mx-auto">
      <h2 className="text-xl font-bold text-gray-100 uppercase tracking-wide mb-6 text-center">Top Engine Plays</h2>

      {plays.map((game: any, idx: number) => (
         <div key={idx} className="bg-[#151c28] border border-gray-800 rounded-xl p-4 sm:p-5 flex justify-between items-center shadow-lg hover:border-gray-600 transition-colors">
           <div className="flex items-center space-x-3 sm:space-x-6">
              <div className="text-3xl sm:text-4xl font-black italic text-[#111827] drop-shadow-[0_1px_1px_rgba(255,255,255,0.2)]">#{idx + 1}</div>
              <div>
                <h3 className="text-base sm:text-xl font-black text-white">{game.away.name} @ {game.home.name}</h3>
                <p className="text-xs sm:text-sm text-gray-400 mt-1">Win Prob: <span className="text-emerald-400 font-bold">{game.prob}</span></p>
              </div>
           </div>
           <div className="text-right">
              <div className="text-emerald-400 font-black text-base sm:text-xl">{game.details.best_angle.play}</div>
              <div className="text-xs text-gray-500 mt-1">
                 Edge: <span className="text-emerald-500 font-bold">{game.edge}</span> | Tier: <span className="text-white font-bold">{game.tier}</span>
              </div>
           </div>
         </div>
      ))}
    </div>
  );
};

// ─── Main Dashboard ────────────────────────────────────────────────────────────
export default function NHLDashboard() {
  const [activeMode, setActiveMode] = useState('daily');
  const [activeDate, setActiveDate] = useState('today');

  return (
    <div className="min-h-screen bg-[#0b0f19] text-gray-100 p-3 sm:p-6 font-sans">
      <div className="max-w-5xl mx-auto space-y-4 sm:space-y-6">

        {/* HEADER & MODES */}
        <div className="flex items-center justify-between border-b border-gray-800 pb-4">
          <h1 className="text-xl sm:text-3xl font-black italic tracking-wider text-white">
            SUMEET<span className="text-blue-500">ENGINE</span> <span className="text-gray-500 text-sm sm:text-lg">NHL</span>
          </h1>
          <div className="flex space-x-1 bg-[#111827] p-1 rounded-lg border border-gray-800">
            {['daily', 'snapshot', 'top'].map((mode) => (
              <button
                key={mode}
                onClick={() => setActiveMode(mode)}
                className={`px-2 sm:px-4 py-1.5 sm:py-2 rounded-md text-[10px] sm:text-sm font-bold uppercase tracking-wide transition-all ${
                  activeMode === mode ? 'bg-blue-600 text-white shadow-md' : 'text-gray-400 hover:text-white'
                }`}
              >
                {mode === 'top' ? 'Top Plays' : mode}
              </button>
            ))}
          </div>
        </div>

        {/* DATE SELECTOR (Only show if in Daily Mode) */}
        {activeMode === 'daily' && (
          <div className="flex justify-center">
            <div className="flex space-x-1 bg-[#111827] p-1 rounded-full border border-gray-800">
              {['yesterday', 'today', 'tomorrow'].map((date) => (
                <button
                  key={date}
                  onClick={() => setActiveDate(date)}
                  className={`px-4 sm:px-6 py-1.5 sm:py-2 rounded-full text-[10px] sm:text-xs font-bold uppercase tracking-wider transition-all ${
                    activeDate === date ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {date}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* MAIN CONTENT AREA */}
        <div className="mt-2 sm:mt-8">
          {activeMode === 'snapshot' && <PerformanceTracker />}

          {activeMode === 'daily' && (
             <div className="space-y-4 sm:space-y-6">
                {/* ⚡ Edge Plays — right under the date toggle */}
                <DailyEdgePlays dateMode={activeDate} />
                {/* @ts-ignore */}
                <NHLMatchupCard dateMode={activeDate} />
             </div>
          )}

          {activeMode === 'top' && <TopPlaysList />}
        </div>

      </div>
    </div>
  );
}