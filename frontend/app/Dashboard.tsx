"use client";

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { easternDate, dateOptions as buildDateOptions, gamesForDate } from '../lib/predictionDates.mjs';
import { publicFile } from '../lib/basePath';
import LegendsHeader, { HeaderTab } from '../components/LegendsHeader';

const MODES = [
  { key: 'daily', icon: '📅', label: 'Daily' },
  { key: 'snapshot', icon: '📊', label: 'Snapshot' },
  { key: 'top', icon: '🔥', label: 'Top Plays' },
];

// ── Dynamic imports with ssr:false — prevents server-side crash ───────────────
const NHLMatchupCard   = dynamic(() => import('../components/NHLMatchupCard'),   { ssr: false });
const PerformanceTracker = dynamic(() => import('../components/PerformanceTracker'), { ssr: false });

// ── Top Plays ─────────────────────────────────────────────────────────────────
const TopPlaysList = ({ payload, today, loading }: { payload: any; today: string; loading: boolean }) => {
  const games = gamesForDate(payload, today);
  const plays = games?.filter((game: any) => ['EDGE', 'BIG'].includes(game.tier)).slice(0, 3);

  if (loading) return (
    <div className="flex justify-center mt-20">
      <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  );

  if (!plays) return <p className="text-center text-gray-400 mt-20">Predictions unavailable for {today} (Eastern Time). Waiting for an update.</p>;

  if (plays.length === 0) return (
    <div className="text-center text-gray-500 mt-20 font-mono text-sm px-4">
      No EDGE or BIG plays found today. Check tomorrow's slate.
    </div>
  );

  return (
    <div className="space-y-4 max-w-3xl mx-auto px-2">
      <h2 className="text-xl font-bold text-gray-100 uppercase tracking-wide mb-6 text-center">Top Engine Plays</h2>
      {plays.map((game: any, idx: number) => (
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

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [activeMode, setActiveMode]   = useState<string>('daily');
  const [activeDate, setActiveDate]   = useState<string>('');
  const [today, setToday] = useState('');
  const [payload, setPayload] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const dateOptions = today ? buildDateOptions(today) : [];

  useEffect(() => {
    let disposed = false;
    let pending = false;
    const controller = new AbortController();
    const refresh = async () => {
      const current = easternDate();
      setToday(current);
      if (pending) return;
      pending = true;
      try {
        const response = await fetch(publicFile('/daily_predictions.json?t=') + Date.now(), {
          cache: 'no-store', signal: controller.signal,
        });
        if (!response.ok) throw new Error('Predictions unavailable');
        const data = await response.json();
        if (!disposed) setPayload(data);
      } catch {
        // Keep the last correctly dated payload during temporary network failures.
      } finally {
        pending = false;
        if (!disposed) setLoading(false);
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 30_000);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      disposed = true;
      controller.abort();
      window.clearInterval(timer);
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, []);

  const selectedDate = dateOptions.some(option => option.key === activeDate) ? activeDate : today;

  return (
    <div className="min-h-screen bg-[#0b0f19] text-gray-100 font-sans">

      {/* The Legends Sports header (client's site, 2026-10-16), with this
          page's modes as its tab row. */}
      <LegendsHeader subtitle="NHL Game Predictions (Beta)">
        {MODES.map(({ key, icon, label }) => (
          <HeaderTab key={key} active={activeMode === key} onClick={() => setActiveMode(key)} icon={icon} label={label} />
        ))}
      </LegendsHeader>

      <div className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-4">

        {/* DATE SELECTOR */}
        {activeMode === 'daily' && (
          <div className="overflow-x-auto pb-1 -mx-3 px-3">
            <p className="text-xs text-gray-400 mb-2 text-center">Dates in Eastern Time</p>
            <div className="flex space-x-2 min-w-max mx-auto w-fit">
              {dateOptions.map(({ key, label, sub }: { key: string; label: string; sub: string }) => (
                <button
                  key={key}
                  onClick={() => setActiveDate(key === today ? '' : key)}
                  className={`flex flex-col items-center px-3 sm:px-5 py-2 sm:py-3 rounded-xl border transition-all ${
                    selectedDate === key
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
          {/* @ts-ignore */}
          {activeMode === 'daily'    && <NHLMatchupCard selectedDate={selectedDate} payload={payload} loading={loading} />}
          {activeMode === 'top'      && <TopPlaysList payload={payload} today={today} loading={loading} />}
        </div>

      </div>
    </div>
  );
}
