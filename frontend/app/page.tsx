"use client";
import React, { useState, useEffect } from 'react';
import NHLMatchupCard from '../components/NHLMatchupCard';
import PerformanceTracker from '../components/PerformanceTracker';

// The new component that reads the "top_plays" array and builds the mini-cards
const TopPlaysList = () => {
  const [plays, setPlays] = useState(null);
  
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
      
      {plays.map((game, idx) => (
         <div key={idx} className="bg-[#151c28] border border-gray-800 rounded-xl p-5 flex justify-between items-center shadow-lg hover:border-gray-600 transition-colors">
           <div className="flex items-center space-x-6">
              <div className="text-4xl font-black italic text-[#111827] drop-shadow-[0_1px_1px_rgba(255,255,255,0.2)]">#{idx + 1}</div>
              <div>
                <h3 className="text-xl font-black text-white">{game.away.name} @ {game.home.name}</h3>
                <p className="text-sm text-gray-400 mt-1">Win Prob: <span className="text-emerald-400 font-bold">{game.prob}</span></p>
              </div>
           </div>
           <div className="text-right">
              <div className="text-emerald-400 font-black text-xl">{game.details.best_angle.play}</div>
              <div className="text-sm text-gray-500 mt-1">
                 Edge: <span className="text-emerald-500 font-bold">{game.edge}</span> | Tier: <span className="text-white font-bold">{game.tier}</span>
              </div>
           </div>
         </div>
      ))}
    </div>
  );
};

export default function NHLDashboard() {
  const [activeMode, setActiveMode] = useState('daily'); 
  const [activeDate, setActiveDate] = useState('today'); 

  return (
    <div className="min-h-screen bg-[#0b0f19] text-gray-100 p-6 font-sans">
      <div className="max-w-5xl mx-auto space-y-6">
        
        {/* HEADER & MODES */}
        <div className="flex items-center justify-between border-b border-gray-800 pb-4">
          <h1 className="text-3xl font-black italic tracking-wider text-white">
            SUMEET<span className="text-blue-500">ENGINE</span> <span className="text-gray-500 text-lg">NHL</span>
          </h1>
          <div className="flex space-x-2 bg-[#111827] p-1 rounded-lg border border-gray-800">
            {['daily', 'snapshot', 'top'].map((mode) => (
              <button
                key={mode}
                onClick={() => setActiveMode(mode)}
                className={`px-4 py-2 rounded-md text-sm font-bold uppercase tracking-wide transition-all ${
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
          <div className="flex justify-center mb-6">
            <div className="flex space-x-1 bg-[#111827] p-1 rounded-full border border-gray-800">
              {['yesterday', 'today', 'tomorrow'].map((date) => (
                <button
                  key={date}
                  onClick={() => setActiveDate(date)}
                  className={`px-6 py-2 rounded-full text-xs font-bold uppercase tracking-wider transition-all ${
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
        <div className="mt-8">
          {activeMode === 'snapshot' && <PerformanceTracker />}
          
          {activeMode === 'daily' && (
             <div className="space-y-6">
                <NHLMatchupCard dateMode={activeDate} />
             </div>
          )}

          {/* This is where your new Top Plays render! */}
          {activeMode === 'top' && <TopPlaysList />}
        </div>

      </div>
    </div>
  );
}