"use client";
import React, { useState, useEffect } from 'react';

const getTeamFullName = (abbrev) => {
    const teams = {
        'VGK': 'Vegas Golden Knights', 'COL': 'Colorado Avalanche', 'BOS': 'Boston Bruins',
        'TOR': 'Toronto Maple Leafs', 'TBL': 'Tampa Bay Lightning', 'FLA': 'Florida Panthers',
        'MTL': 'Montreal Canadiens', 'OTT': 'Ottawa Senators', 'BUF': 'Buffalo Sabres',
        'DET': 'Detroit Red Wings', 'CAR': 'Carolina Hurricanes', 'NJD': 'New Jersey Devils',
        'NYR': 'New York Rangers', 'WSH': 'Washington Capitals', 'NYI': 'New York Islanders',
        'PIT': 'Pittsburgh Penguins', 'PHI': 'Philadelphia Flyers', 'CBJ': 'Columbus Blue Jackets',
        'DAL': 'Dallas Stars', 'WPG': 'Winnipeg Jets', 'NSH': 'Nashville Predators',
        'STL': 'St. Louis Blues', 'MIN': 'Minnesota Wild', 'ARI': 'Arizona Coyotes',
        'CHI': 'Chicago Blackhawks', 'VAN': 'Vancouver Canucks', 'EDM': 'Edmonton Oilers',
        'LAK': 'Los Angeles Kings', 'SEA': 'Seattle Kraken', 'CGY': 'Calgary Flames',
        'SJS': 'San Jose Sharks', 'ANA': 'Anaheim Ducks', 'UTA': 'Utah Hockey Club'
    };
    return teams[abbrev] || abbrev;
};

const NHLMatchupCard = ({ dateMode }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [allGames, setAllGames] = useState(null);
  const [loading, setLoading] = useState(true);
  
  const [activeLogTab, setActiveLogTab] = useState('h2h'); 

  useEffect(() => {
    const fetchGameData = () => {
      fetch('/daily_predictions.json?t=' + new Date().getTime())
        .then(async (res) => {
          if (!res.ok) throw new Error("Could not load daily predictions");
          return res.json();
        })
        .then((json) => {
          setAllGames(json);
          setLoading(false);
        })
        .catch((err) => {
          setTimeout(fetchGameData, 1500); 
        });
    };
    fetchGameData();
  }, []);

  if (loading) {
    return (
      <div className="bg-[#151c28] rounded-xl border border-gray-800 shadow-2xl h-80 flex flex-col items-center justify-center">
        <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-3"></div>
        <p className="text-gray-500 font-mono text-xs uppercase tracking-widest animate-pulse">Running Matchups...</p>
      </div>
    );
  }

  const game = allGames ? allGames[dateMode] : null;

  if (!game) {
    return (
      <div className="bg-[#151c28] rounded-xl border border-gray-800 shadow-2xl h-64 flex flex-col items-center justify-center">
        <p className="text-gray-500 font-mono text-sm uppercase tracking-widest">No scheduled games for {dateMode}</p>
      </div>
    );
  }

  // 🚨 THE FIX: Perfectly identify the predicted winner and exact probability
  const predictedWinner = game.details.best_angle.play.split(' ')[0];
  const maxProb = parseFloat(game.prob);

  return (
    <div className="bg-[#151c28] rounded-xl border border-gray-800 shadow-2xl overflow-hidden transition-all font-sans">
      
      {/* --- TOP SUMMARY CARD --- */}
      <div className="p-6 relative">
          
        <div className="flex justify-between items-start mb-6">
          
          <div className="flex flex-col items-center w-4/12">
            <div className="w-24 h-24 bg-[#111827] rounded-full border border-gray-700 flex items-center justify-center mb-3 overflow-hidden shadow-inner p-2">
               <img 
                  src={`https://a.espncdn.com/i/teamlogos/nhl/500/scoreboard/${game.away.name.toLowerCase()}.png`} 
                  alt={game.away.name} 
                  className="w-16 h-16 object-contain drop-shadow-lg" 
                  onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='block'; }} 
               />
               <span className="hidden text-2xl font-black text-gray-400">{game.away.name}</span>
            </div>
            <h2 className="text-lg font-bold text-white text-center leading-tight">{getTeamFullName(game.away.name)}</h2>
             <div className="mt-3 bg-[#0b0f19] border border-gray-700 px-6 py-2 rounded-md text-emerald-400 font-black text-lg shadow-sm whitespace-nowrap">
              {game.away.ml}
            </div>
          </div>

          <div className="flex flex-col items-center justify-start w-4/12 pt-1 space-y-1">
            <span className="text-[11px] font-bold text-gray-400 uppercase tracking-widest whitespace-nowrap bg-gray-800/50 px-3 py-1 rounded-full mb-1">{game.time}</span>
            <span className="text-gray-500 font-black text-3xl">@</span>
            <span className="text-xs font-bold text-gray-300 tracking-widest whitespace-nowrap pb-2">{game.ou_total}</span>
            
            <div className="w-full flex flex-col space-y-1.5 mt-2">
                <div className="bg-[#111827] border border-gray-800 rounded px-3 py-1.5 flex items-center w-full shadow-inner">
                    <span className="w-1/3 text-left text-[10px] text-gray-300 font-mono font-bold">{game.away.record_overall}</span>
                    <span className="w-1/3 text-center text-[9px] text-gray-500 font-bold uppercase tracking-widest">OVR</span>
                    <span className="w-1/3 text-right text-[10px] text-gray-300 font-mono font-bold">{game.home.record_overall}</span>
                </div>
                <div className="bg-[#111827] border border-gray-800 rounded px-3 py-1.5 flex items-center w-full shadow-inner">
                    <span className="w-1/3 text-left text-[10px] text-gray-300 font-mono font-bold">{game.away.record_split}</span>
                    <span className="w-1/3 text-center text-[9px] text-gray-500 font-bold uppercase tracking-widest">A/H</span>
                    <span className="w-1/3 text-right text-[10px] text-gray-300 font-mono font-bold">{game.home.record_split}</span>
                </div>
                <div className="bg-[#111827] border border-gray-800 rounded px-3 py-1.5 flex items-center w-full shadow-inner">
                    <span className="w-1/3 text-left text-[10px] text-gray-300 font-mono font-bold">{game.away.record_l10}</span>
                    <span className="w-1/3 text-center text-[9px] text-gray-500 font-bold uppercase tracking-widest">L10</span>
                    <span className="w-1/3 text-right text-[10px] text-gray-300 font-mono font-bold">{game.home.record_l10}</span>
                </div>
            </div>
          </div>

          <div className="flex flex-col items-center w-4/12">
            <div className="w-24 h-24 bg-[#111827] rounded-full border border-gray-700 flex items-center justify-center mb-3 overflow-hidden shadow-inner p-2">
                <img 
                  src={`https://a.espncdn.com/i/teamlogos/nhl/500/scoreboard/${game.home.name.toLowerCase()}.png`} 
                  alt={game.home.name} 
                  className="w-16 h-16 object-contain drop-shadow-lg" 
                  onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='block'; }} 
               />
               <span className="hidden text-2xl font-black text-gray-400">{game.home.name}</span>
            </div>
            <h2 className="text-lg font-bold text-white text-center leading-tight">{getTeamFullName(game.home.name)}</h2>
            <div className="mt-3 bg-[#0b0f19] border border-gray-700 px-6 py-2 rounded-md text-emerald-400 font-black text-lg shadow-sm whitespace-nowrap">
              {game.home.ml}
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-[#0b0f19] via-[#111827] to-[#0b0f19] border border-emerald-900/30 rounded-xl p-4 shadow-inner flex items-center justify-around mt-4">
             {/* 🚨 THE FIX: Dynamically assign the maxProb to the confirmed winner */}
             <div className="flex flex-col items-center">
                 <p className="text-[10px] uppercase tracking-widest text-gray-500 mb-1 font-bold">{game.away.name} Win Prob</p>
                 <p className={`text-2xl font-black ${predictedWinner === game.away.name ? 'text-emerald-400' : 'text-gray-300'}`}>
                   {(predictedWinner === game.away.name ? maxProb : 100 - maxProb).toFixed(1)}%
                 </p>
             </div>
             
             <div className="flex flex-col items-center border-l border-r border-gray-800 px-10">
                 <p className="text-[10px] uppercase tracking-widest text-emerald-500/70 mb-1 font-bold">Projected Score</p>
                 <div className="flex items-center space-x-3">
                     <span className={`text-3xl font-black drop-shadow-md ${predictedWinner === game.away.name ? 'text-emerald-400' : 'text-white'}`}>{game.away.proj}</span>
                     <span className="text-gray-600 font-bold text-xl">-</span>
                     <span className={`text-3xl font-black drop-shadow-md ${predictedWinner === game.home.name ? 'text-emerald-400' : 'text-white'}`}>{game.home.proj}</span>
                 </div>
             </div>
             
             <div className="flex flex-col items-center">
                 <p className="text-[10px] uppercase tracking-widest text-emerald-500/70 mb-1 font-bold">{game.home.name} Win Prob</p>
                 <p className={`text-2xl font-black ${predictedWinner === game.home.name ? 'text-emerald-400' : 'text-gray-300'}`}>
                   {(predictedWinner === game.home.name ? maxProb : 100 - maxProb).toFixed(1)}%
                 </p>
             </div>
        </div>
      </div>

      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full bg-[#1b2436] hover:bg-[#232f46] border-t border-gray-800 py-3.5 text-xs font-bold text-gray-300 uppercase tracking-widest transition-colors flex justify-center items-center group shadow-md"
      >
        {isExpanded ? 'Collapse Matchup Details ▲' : 'View Matchup Details ▼'}
      </button>

      {/* --- EXPANDED DETAILS SECTION --- */}
      {isExpanded && (
        <div className="bg-[#0b0f19] p-6 border-t border-gray-800 flex flex-col space-y-6">
          
          <div className="bg-[#111827] rounded-lg border border-gray-800 p-4">
             <h4 className="text-sm text-gray-300 uppercase tracking-widest font-black mb-4 border-b border-gray-700 pb-2 flex items-center">
                 <span className="w-1.5 h-4 bg-blue-500 mr-2 rounded-sm"></span>
                 Period Analysis & Projections
             </h4>
             <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                 <div className="space-y-3 text-sm text-gray-400">
                  <div className="flex justify-between border-b border-gray-800/50 pb-1"><span>1st Period Winner:</span> <span className="font-bold text-blue-400">{game.details.period_60.p1_winner}</span></div>
                  <div className="flex justify-between border-b border-gray-800/50 pb-1"><span>1st Period Over 1.5:</span> <span className="font-bold text-white">{game.details.period_60.p1_over_1_5}</span></div>
                  <div className="flex justify-between"><span>60 Min Regulation Tie:</span> <span className="font-bold text-gray-400">{game.details.period_60.min_60_tie}</span></div>
                 </div>
                 
                 <div className="space-y-3 text-sm text-gray-400">
                    {['p1', 'p2', 'p3'].map((pKey) => {
                        const scoreString = game.details.period_scores[pKey] || "";
                        if (!scoreString.includes(' - ')) return null;

                        const [awayPart, homePart] = scoreString.split(' - ');
                        const awayTeam = awayPart.split(' ')[0];
                        const awayScore = awayPart.split(' ')[1];
                        const homeTeam = homePart.split(' ')[0];
                        const homeScore = homePart.split(' ')[1];
                        
                        return (
                            <div key={pKey} className="flex justify-between border-b border-gray-800/50 pb-1 last:border-b-0">
                                <span className="uppercase">{pKey} Proj Score:</span>
                                <div className="font-mono text-gray-200">
                                    <span className={predictedWinner === awayTeam ? "text-emerald-400 font-bold" : ""}>{awayScore}</span>
                                    <span className="text-gray-600 mx-1">-</span>
                                    <span className={predictedWinner === homeTeam ? "text-emerald-400 font-bold" : ""}>{homeScore}</span>
                                </div>
                            </div>
                        );
                    })}
                 </div>
             </div>
          </div>

          <div className="bg-[#111827] rounded-lg border border-gray-800 p-4">
             <h4 className="text-sm text-gray-300 uppercase tracking-widest font-black mb-4 border-b border-gray-700 pb-2 flex items-center">
                 <span className="w-1.5 h-4 bg-purple-500 mr-2 rounded-sm"></span>
                 Game Notes & Context
             </h4>
             <ul className="text-sm text-gray-400 space-y-2 list-none pl-2">
                  {game.details.notes.map((note, idx) => (
                    <li key={idx} className="flex items-start">
                        <span className="text-purple-500 mr-2 mt-0.5 text-xs">▶</span>
                        {note}
                    </li>
                  ))}
             </ul>
          </div>

           <div className="bg-[#111827] rounded-lg border border-gray-800 p-4">
             <div className="flex items-center justify-between border-b border-gray-700 mb-4 pb-2">
                 <h4 className="text-sm text-gray-300 uppercase tracking-widest font-black flex items-center">
                     <span className="w-1.5 h-4 bg-orange-500 mr-2 rounded-sm"></span>
                     Recent Form (L10)
                 </h4>
                 <div className="flex space-x-1 bg-[#0b0f19] p-1 rounded-md border border-gray-800">
                     <button onClick={() => setActiveLogTab('away')} className={`px-3 py-1 text-[10px] font-bold uppercase rounded ${activeLogTab === 'away' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'}`}>{game.away.name}</button>
                     <button onClick={() => setActiveLogTab('h2h')} className={`px-3 py-1 text-[10px] font-bold uppercase rounded ${activeLogTab === 'h2h' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-300'}`}>H2H</button>
                     <button onClick={() => setActiveLogTab('home')} className={`px-3 py-1 text-[10px] font-bold uppercase rounded ${activeLogTab === 'home' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'}`}>{game.home.name}</button>
                 </div>
             </div>
             
             <div className="space-y-1.5">
                {game.details.recent_logs[activeLogTab]?.map((log, idx) => (
                    <div key={idx} className="flex items-center justify-between bg-[#0b0f19] border border-gray-800/50 p-2 rounded">
                        <div className="flex items-center w-1/3">
                            <span className="text-[10px] text-gray-500 font-mono mr-3">{log.date}</span>
                            <span className="text-xs font-bold text-gray-300">{log.opp}</span>
                        </div>
                        <div className="w-1/3 flex justify-center">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-black ${log.result === 'W' ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-800/50' : 'bg-red-900/20 text-red-400 border border-red-900/30'}`}>
                                {log.result}
                            </span>
                        </div>
                        <div className="w-1/3 text-right">
                            <span className="text-xs font-mono text-gray-400 font-bold">{log.score}</span>
                        </div>
                    </div>
                ))}
             </div>
          </div>

           <div className="bg-gradient-to-br from-[#1a2e23] to-[#111827] rounded-lg border border-emerald-900/50 p-5 shadow-lg relative overflow-hidden">
             <h4 className="text-lg text-emerald-400 uppercase tracking-widest font-black mb-4 border-b border-emerald-900/50 pb-2 flex items-center z-10 relative">
                 <span className="w-2 h-5 bg-emerald-500 mr-2 rounded-sm shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
                 Legends Sports Predictions
             </h4>
             
             <div className="grid grid-cols-1 md:grid-cols-2 gap-6 z-10 relative">
                 <div className="space-y-3 text-sm text-gray-300 bg-[#0b0f19]/60 p-4 rounded border border-emerald-900/30">
                  <div className="flex justify-between items-center border-b border-emerald-900/30 pb-2">
                      <span className="text-xs uppercase tracking-widest text-gray-400">Best ML Value</span> 
                      <span className="font-black text-white">{game.details.covers.best_ml}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-emerald-900/30 pb-2">
                      <span className="text-xs uppercase tracking-widest text-gray-400">Best Spread</span> 
                      <span className="font-black text-gray-400">{game.details.covers.best_spread}</span>
                  </div>
                  <div className="flex justify-between items-center">
                      <span className="text-xs uppercase tracking-widest text-gray-400">Best O/U</span> 
                      <span className="font-black text-blue-400">{game.details.covers.best_ou}</span>
                  </div>
                 </div>

                 <div className="flex flex-col justify-center items-center space-y-4">
                     <div className="text-center w-full bg-[#0b0f19]/80 p-4 rounded border border-emerald-800/50 shadow-inner">
                         <h5 className="text-[10px] text-emerald-500 font-bold uppercase tracking-widest mb-1">Official Best Angle Play</h5>
                         <p className="text-2xl font-black text-emerald-400 drop-shadow-[0_0_10px_rgba(16,185,129,0.3)]">{game.details.best_angle.play}</p>
                     </div>
                     
                     <div className="flex items-center space-x-3 w-full justify-center">
                         <span className="text-xs font-bold text-gray-400 uppercase tracking-widest mt-1">AI Confidence Score</span>
                         <div className="flex items-end bg-[#111827] px-3 py-1 rounded-md border border-gray-700">
                            <span className="text-2xl font-black text-white">{game.ai_score}</span>
                            <span className="text-xs font-bold text-gray-500 mb-1 ml-1">/ 10</span>
                         </div>
                     </div>
                 </div>
             </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NHLMatchupCard;