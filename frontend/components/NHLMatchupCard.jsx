"use client";
import React, { useState, useEffect } from 'react';

// ── GIFT Stats Component ───────────────────────────────────────────────────────
const GiftStatTeamCard = ({ team, data, isHome }) => {
  const [tab, setTab] = useState('season');

  const pctMap = {
    season: data?.pct_season || 'N/A',
    l5:     data?.pct_l5     || 'N/A',
    l10:    data?.pct_l10    || 'N/A',
  };

  const pct     = pctMap[tab];
  const pctNum  = parseFloat(pct) || 0;
  const pctColor = pctNum >= 65 ? 'text-emerald-400' : pctNum >= 55 ? 'text-yellow-400' : 'text-red-400';
  const streak  = data?.streak || 0;

  return (
    <div className="bg-[#0b0f19] border border-gray-800 rounded-lg p-3 sm:p-4 flex-1">
      {/* Team header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <img
            src={`https://a.espncdn.com/i/teamlogos/nhl/500/scoreboard/${team.toLowerCase()}.png`}
            alt={team}
            className="w-7 h-7 object-contain"
            onError={e => { e.target.style.display='none'; }}
          />
          <span className="text-sm font-black text-white">{team}</span>
        </div>
        {streak > 0 && (
          <span className="text-[9px] font-black uppercase px-1.5 py-0.5 rounded bg-yellow-900/30 text-yellow-400 border border-yellow-800/30">
            🔥 {streak} streak
          </span>
        )}
      </div>

      {/* Season / L5 / L10 tabs */}
      <div className="flex space-x-1 bg-[#111827] p-0.5 rounded mb-3">
        {['season','l5','l10'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-1 text-[9px] font-bold uppercase rounded transition-all ${
              tab === t ? 'bg-yellow-600/80 text-white' : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {t === 'season' ? 'Season' : t.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Main percentage */}
      <div className="text-center mb-3">
        <p className={`text-3xl font-black ${pctColor}`}>{pct}</p>
        <p className="text-[9px] uppercase tracking-widest text-gray-600 mt-0.5">GIFT Rate</p>
      </div>

      {/* Record */}
      {data?.record_season && data.record_season !== 'N/A' && (
        <div className="flex justify-between text-[10px] border-t border-gray-800 pt-2 mb-2">
          <span className="text-gray-500">Record</span>
          <span className="font-bold text-white">{data.record_season}</span>
        </div>
      )}

      {/* Home / Away split */}
      <div className="flex space-x-2">
        {data?.home_pct && data.home_pct !== 'N/A' && (
          <div className="flex-1 bg-[#111827] rounded p-1.5 text-center">
            <p className="text-[8px] uppercase text-gray-600">🏠 Home</p>
            <p className="text-xs font-black text-emerald-400">{data.home_pct}</p>
          </div>
        )}
        {data?.away_pct && data.away_pct !== 'N/A' && (
          <div className="flex-1 bg-[#111827] rounded p-1.5 text-center">
            <p className="text-[8px] uppercase text-gray-600">✈️ Away</p>
            <p className="text-xs font-black text-blue-400">{data.away_pct}</p>
          </div>
        )}
      </div>
    </div>
  );
};

const GiftStatsSection = ({ giftStats, awayTeam, homeTeam }) => (
  <div className="bg-[#111827] rounded-lg border border-yellow-900/40 p-3 sm:p-4">
    <h4 className="text-sm text-yellow-400 uppercase tracking-widest font-black mb-4 border-b border-yellow-900/30 pb-2 flex items-center">
      <span className="w-1.5 h-4 bg-yellow-500 mr-2 rounded-sm shadow-[0_0_6px_rgba(234,179,8,0.6)]"></span>
      ⚡ GIFT — Goals In First 10 Min
    </h4>
    <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-3 font-mono">
      % of games with a goal in the first 10 minutes of play
    </p>
    <div className="flex space-x-3">
      <GiftStatTeamCard team={awayTeam} data={giftStats?.away} />
      <GiftStatTeamCard team={homeTeam} data={giftStats?.home} />
    </div>
  </div>
);

// ── First Period O/U Component ─────────────────────────────────────────────────
const FirstPeriodSection = ({ fpStats, awayTeam, homeTeam }) => {
  const away = fpStats?.away;
  const home = fpStats?.home;
  const TeamFP = ({ team, data }) => {
    const [tab, setTab] = React.useState('season');
    const pctMap = {
      season: data?.pct_season || 'N/A',
      l5:     data?.pct_l5     || 'N/A',
      l10:    data?.pct_l10    || 'N/A',
    };
    const pct    = pctMap[tab];
    const pctNum = parseFloat(pct) || 0;
    const color  = pctNum >= 60 ? 'text-emerald-400' : pctNum >= 50 ? 'text-yellow-400' : 'text-red-400';
    return (
      <div className="flex-1 bg-[#0b0f19] border border-gray-800 rounded-lg p-3">
        {/* Team header */}
        <div className="flex items-center space-x-2 mb-3">
          <img
            src={`https://a.espncdn.com/i/teamlogos/nhl/500/scoreboard/${team.toLowerCase()}.png`}
            alt={team} className="w-6 h-6 object-contain"
            onError={e => { e.target.style.display='none'; }}
          />
          <span className="text-xs font-black text-white">{team}</span>
        </div>
        {/* Season / L5 / L10 tabs */}
        <div className="flex space-x-1 bg-[#111827] p-0.5 rounded mb-3">
          {['season', 'l5', 'l10'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-1 text-[9px] font-bold uppercase rounded transition-all ${
                tab === t ? 'bg-blue-600/80 text-white' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {t === 'season' ? 'Season' : t.toUpperCase()}
            </button>
          ))}
        </div>
        {/* Main percentage */}
        <div className="text-center mb-3">
          <p className={`text-2xl font-black ${color}`}>{pct}</p>
          <p className="text-[9px] uppercase tracking-widest text-gray-600 mt-0.5">1st Period O/U Rate</p>
        </div>
        {/* Record */}
        {data?.record_season && data.record_season !== 'N/A' && (
          <div className="flex justify-between text-[10px] border-t border-gray-800 pt-2 mb-2">
            <span className="text-gray-500">Record</span>
            <span className="font-bold text-white">{data.record_season}</span>
          </div>
        )}
        {/* Home / Away split */}
        <div className="flex space-x-1 mt-1">
          {data?.home_pct && data.home_pct !== 'N/A' && (
            <div className="flex-1 bg-[#111827] rounded p-1 text-center">
              <p className="text-[8px] text-gray-600">Home</p>
              <p className="text-[10px] font-black text-emerald-400">{data.home_pct}</p>
            </div>
          )}
          {data?.away_pct && data.away_pct !== 'N/A' && (
            <div className="flex-1 bg-[#111827] rounded p-1 text-center">
              <p className="text-[8px] text-gray-600">Away</p>
              <p className="text-[10px] font-black text-blue-400">{data.away_pct}</p>
            </div>
          )}
        </div>
      </div>
    );
  };
  return (
    <div className="bg-[#111827] rounded-lg border border-blue-900/40 p-3 sm:p-4">
      <h4 className="text-sm text-blue-400 uppercase tracking-widest font-black mb-4 border-b border-blue-900/30 pb-2 flex items-center">
        <span className="w-1.5 h-4 bg-blue-500 mr-2 rounded-sm shadow-[0_0_6px_rgba(59,130,246,0.6)]"></span>
        📊 1st Period Over/Under Trends
      </h4>
      <div className="flex space-x-3">
        <TeamFP team={awayTeam} data={away} />
        <TeamFP team={homeTeam} data={home} />
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
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

// ── Single game card (reusable) ─────────────────────────────────────────────
const SingleMatchupCard = ({ game, giftStatsAll, defaultExpanded = false }) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [activeLogTab, setActiveLogTab] = useState('h2h');

  const predictedWinner = game.details.best_angle.play.split(' ')[0];
  const maxProb = parseFloat(game.prob);

  // Compute W-L summary for each log tab
  const getRecord = (logs) => {
    if (!logs?.length) return null;
    const w = logs.filter(l => l.result === 'W').length;
    return { w, l: logs.length - w };
  };

  const awayRecord = getRecord(game.details.recent_logs?.away);
  const homeRecord = getRecord(game.details.recent_logs?.home);
  const h2hRecord  = getRecord(game.details.recent_logs?.h2h);

  return (
    <div className="bg-[#151c28] rounded-xl border border-gray-800 shadow-2xl overflow-hidden transition-all font-sans">

      {/* --- TOP SUMMARY CARD --- */}
      <div className="p-3 sm:p-6 relative">

        <div className="flex justify-between items-start mb-4 sm:mb-6">

          {/* Away Team */}
          <div className="flex flex-col items-center w-[38%] sm:w-4/12">
            <div className="w-16 h-16 sm:w-24 sm:h-24 bg-[#111827] rounded-full border border-gray-700 flex items-center justify-center mb-2 sm:mb-3 overflow-hidden shadow-inner p-1 sm:p-2">
               <img
                  src={`https://a.espncdn.com/i/teamlogos/nhl/500/scoreboard/${game.away.name.toLowerCase()}.png`}
                  alt={game.away.name}
                  className="w-12 h-12 sm:w-16 sm:h-16 object-contain drop-shadow-lg"
                  onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='block'; }}
               />
               <span className="hidden text-lg sm:text-2xl font-black text-gray-400">{game.away.name}</span>
            </div>
            <h2 className="text-[11px] sm:text-lg font-bold text-white text-center leading-tight px-1">{getTeamFullName(game.away.name)}</h2>
            <div className="mt-2 sm:mt-3 bg-[#0b0f19] border border-gray-700 px-2 sm:px-6 py-1 sm:py-2 rounded-md text-emerald-400 font-black text-sm sm:text-lg shadow-sm whitespace-nowrap">
              {game.away.ml}
            </div>
          </div>

          {/* Center Info */}
          <div className="flex flex-col items-center justify-start w-[24%] sm:w-4/12 pt-1 space-y-1">
            <span className="text-[9px] sm:text-[11px] font-bold text-gray-400 uppercase tracking-widest whitespace-nowrap bg-gray-800/50 px-2 sm:px-3 py-1 rounded-full mb-1">{game.time}</span>
            <span className="text-gray-500 font-black text-2xl sm:text-3xl">@</span>
            <span className="text-[10px] sm:text-xs font-bold text-gray-300 tracking-widest whitespace-nowrap pb-2">{game.ou_total}</span>

            <div className="w-full flex flex-col space-y-1 sm:space-y-1.5 mt-1 sm:mt-2">
                <div className="bg-[#111827] border border-gray-800 rounded px-1.5 sm:px-3 py-1 sm:py-1.5 flex items-center w-full shadow-inner">
                    <span className="w-1/3 text-left text-[7px] sm:text-[10px] text-gray-300 font-mono font-bold">{game.away.record_overall}</span>
                    <span className="w-1/3 text-center text-[6px] sm:text-[9px] text-gray-500 font-bold uppercase tracking-widest">OVR</span>
                    <span className="w-1/3 text-right text-[7px] sm:text-[10px] text-gray-300 font-mono font-bold">{game.home.record_overall}</span>
                </div>
                <div className="bg-[#111827] border border-gray-800 rounded px-1.5 sm:px-3 py-1 sm:py-1.5 flex items-center w-full shadow-inner">
                    <span className="w-1/3 text-left text-[7px] sm:text-[10px] text-gray-300 font-mono font-bold">{game.away.record_split}</span>
                    <span className="w-1/3 text-center text-[6px] sm:text-[9px] text-gray-500 font-bold uppercase tracking-widest">A/H</span>
                    <span className="w-1/3 text-right text-[7px] sm:text-[10px] text-gray-300 font-mono font-bold">{game.home.record_split}</span>
                </div>
                <div className="bg-[#111827] border border-gray-800 rounded px-1.5 sm:px-3 py-1 sm:py-1.5 flex items-center w-full shadow-inner">
                    <span className="w-1/3 text-left text-[7px] sm:text-[10px] text-gray-300 font-mono font-bold">{game.away.record_l10}</span>
                    <span className="w-1/3 text-center text-[6px] sm:text-[9px] text-gray-500 font-bold uppercase tracking-widest">L10</span>
                    <span className="w-1/3 text-right text-[7px] sm:text-[10px] text-gray-300 font-mono font-bold">{game.home.record_l10}</span>
                </div>
            </div>
          </div>

          {/* Home Team */}
          <div className="flex flex-col items-center w-[38%] sm:w-4/12">
            <div className="w-16 h-16 sm:w-24 sm:h-24 bg-[#111827] rounded-full border border-gray-700 flex items-center justify-center mb-2 sm:mb-3 overflow-hidden shadow-inner p-1 sm:p-2">
                <img
                  src={`https://a.espncdn.com/i/teamlogos/nhl/500/scoreboard/${game.home.name.toLowerCase()}.png`}
                  alt={game.home.name}
                  className="w-12 h-12 sm:w-16 sm:h-16 object-contain drop-shadow-lg"
                  onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='block'; }}
               />
               <span className="hidden text-lg sm:text-2xl font-black text-gray-400">{game.home.name}</span>
            </div>
            <h2 className="text-[11px] sm:text-lg font-bold text-white text-center leading-tight px-1">{getTeamFullName(game.home.name)}</h2>
            <div className="mt-2 sm:mt-3 bg-[#0b0f19] border border-gray-700 px-2 sm:px-6 py-1 sm:py-2 rounded-md text-emerald-400 font-black text-sm sm:text-lg shadow-sm whitespace-nowrap">
              {game.home.ml}
            </div>
          </div>
        </div>

        {/* Win Prob / Projected Score Bar */}
        <div className="bg-gradient-to-r from-[#0b0f19] via-[#111827] to-[#0b0f19] border border-emerald-900/30 rounded-xl p-3 sm:p-4 shadow-inner flex items-center justify-around mt-3 sm:mt-4">
             <div className="flex flex-col items-center">
                 <p className="text-[8px] sm:text-[10px] uppercase tracking-widest text-gray-500 mb-1 font-bold">{game.away.name} Win</p>
                 <p className={`text-lg sm:text-2xl font-black ${predictedWinner === game.away.name ? 'text-emerald-400' : 'text-gray-300'}`}>
                   {(predictedWinner === game.away.name ? maxProb : 100 - maxProb).toFixed(1)}%
                 </p>
             </div>

             <div className="flex flex-col items-center border-l border-r border-gray-800 px-3 sm:px-10">
                 <p className="text-[8px] sm:text-[10px] uppercase tracking-widest text-emerald-500/70 mb-1 font-bold">Projected Score</p>
                 <div className="flex items-center space-x-2 sm:space-x-3">
                     <span className={`text-2xl sm:text-3xl font-black drop-shadow-md ${predictedWinner === game.away.name ? 'text-emerald-400' : 'text-white'}`}>{game.away.proj}</span>
                     <span className="text-gray-600 font-bold text-lg sm:text-xl">-</span>
                     <span className={`text-2xl sm:text-3xl font-black drop-shadow-md ${predictedWinner === game.home.name ? 'text-emerald-400' : 'text-white'}`}>{game.home.proj}</span>
                 </div>
             </div>

             <div className="flex flex-col items-center">
                 <p className="text-[8px] sm:text-[10px] uppercase tracking-widest text-emerald-500/70 mb-1 font-bold">{game.home.name} Win</p>
                 <p className={`text-lg sm:text-2xl font-black ${predictedWinner === game.home.name ? 'text-emerald-400' : 'text-gray-300'}`}>
                   {(predictedWinner === game.home.name ? maxProb : 100 - maxProb).toFixed(1)}%
                 </p>
             </div>
        </div>
      </div>

      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full bg-[#1b2436] hover:bg-[#232f46] border-t border-gray-800 py-2.5 sm:py-3.5 text-xs font-bold text-gray-300 uppercase tracking-widest transition-colors flex justify-center items-center shadow-md"
      >
        {isExpanded ? 'Collapse Matchup Details ▲' : 'View Matchup Details ▼'}
      </button>

      {/* --- EXPANDED DETAILS SECTION --- */}
      {isExpanded && (
        <div className="bg-[#0b0f19] p-4 sm:p-6 border-t border-gray-800 flex flex-col space-y-5 sm:space-y-6">

          {/* Period Analysis */}
          <div className="bg-[#111827] rounded-lg border border-gray-800 p-3 sm:p-4">
             <h4 className="text-sm text-gray-300 uppercase tracking-widest font-black mb-4 border-b border-gray-700 pb-2 flex items-center">
                 <span className="w-1.5 h-4 bg-blue-500 mr-2 rounded-sm"></span>
                 Period Analysis & Projections
             </h4>
             <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
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

          {/* Game Notes */}
          <div className="bg-[#111827] rounded-lg border border-gray-800 p-3 sm:p-4">
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

          {/* Recent Form (L10) */}
          <div className="bg-[#111827] rounded-lg border border-gray-800 p-3 sm:p-4">
             <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-gray-700 mb-4 pb-2 gap-2">
                 <h4 className="text-sm text-gray-300 uppercase tracking-widest font-black flex items-center">
                     <span className="w-1.5 h-4 bg-orange-500 mr-2 rounded-sm"></span>
                     Recent Form (L10)
                 </h4>
                 <div className="flex space-x-1 bg-[#0b0f19] p-1 rounded-md border border-gray-800">
                     <button
                       onClick={() => setActiveLogTab('away')}
                       className={`flex-1 sm:flex-none px-2 sm:px-3 py-1 text-[10px] font-bold uppercase rounded transition-colors ${activeLogTab === 'away' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'}`}
                     >
                       {game.away.name}
                       {awayRecord && <span className="ml-1 opacity-60">{awayRecord.w}-{awayRecord.l}</span>}
                     </button>
                     <button
                       onClick={() => setActiveLogTab('h2h')}
                       className={`flex-1 sm:flex-none px-2 sm:px-3 py-1 text-[10px] font-bold uppercase rounded transition-colors ${activeLogTab === 'h2h' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-300'}`}
                     >
                       H2H
                       {h2hRecord && <span className="ml-1 opacity-70">{h2hRecord.w}-{h2hRecord.l}</span>}
                     </button>
                     <button
                       onClick={() => setActiveLogTab('home')}
                       className={`flex-1 sm:flex-none px-2 sm:px-3 py-1 text-[10px] font-bold uppercase rounded transition-colors ${activeLogTab === 'home' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'}`}
                     >
                       {game.home.name}
                       {homeRecord && <span className="ml-1 opacity-60">{homeRecord.w}-{homeRecord.l}</span>}
                     </button>
                 </div>
             </div>

             {/* Tab label */}
             <p className="text-[10px] text-gray-600 uppercase tracking-widest mb-2 font-mono">
               {activeLogTab === 'h2h'
                 ? `Head-to-Head: ${game.away.name} vs ${game.home.name}`
                 : activeLogTab === 'away'
                   ? `${game.away.name} — Last 10 Games`
                   : `${game.home.name} — Last 10 Games`
               }
             </p>

             <div className="space-y-1.5">
                {game.details.recent_logs[activeLogTab]?.map((log, idx) => (
                    <div key={idx} className="flex items-center justify-between bg-[#0b0f19] border border-gray-800/50 p-2 rounded">
                        <div className="flex items-center w-1/3">
                            <span className="text-[10px] text-gray-500 font-mono mr-2 sm:mr-3">{log.date}</span>
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

          {/* GIFT Stats — Goals In First Ten Minutes */}
          {(() => {
            const awayAbbr = game.away.name.toUpperCase();
            const homeAbbr = game.home.name.toUpperCase();
            // Read from gift_stats.json (fetched separately) — fall back to embedded
            const awayGift = giftStatsAll?.[awayAbbr]?.gift || game.details.gift_stats?.away;
            const homeGift = giftStatsAll?.[homeAbbr]?.gift || game.details.gift_stats?.home;
            const awayFp   = giftStatsAll?.[awayAbbr]?.fp_ou || game.details.fp_stats?.away;
            const homeFp   = giftStatsAll?.[homeAbbr]?.fp_ou || game.details.fp_stats?.home;
            return (
              <>
                <GiftStatsSection
                  giftStats={{ away: awayGift, home: homeGift }}
                  awayTeam={game.away.name}
                  homeTeam={game.home.name}
                />
                <FirstPeriodSection
                  fpStats={{ away: awayFp, home: homeFp }}
                  awayTeam={game.away.name}
                  homeTeam={game.home.name}
                />
              </>
            );
          })()}

          {/* Legends Sports Predictions */}
          <div className="bg-gradient-to-br from-[#1a2e23] to-[#111827] rounded-lg border border-emerald-900/50 p-4 sm:p-5 shadow-lg relative overflow-hidden">
             <h4 className="text-base sm:text-lg text-emerald-400 uppercase tracking-widest font-black mb-4 border-b border-emerald-900/50 pb-2 flex items-center z-10 relative">
                 <span className="w-2 h-5 bg-emerald-500 mr-2 rounded-sm shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
                 Legends Sports Predictions
             </h4>

             <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6 z-10 relative">
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
                         <p className="text-xl sm:text-2xl font-black text-emerald-400 drop-shadow-[0_0_10px_rgba(16,185,129,0.3)]">{game.details.best_angle.play}</p>
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
}; // end SingleMatchupCard

// ── Main NHLMatchupCard — fetches data, renders multiple game cards ────────────
const NHLMatchupCard = ({ dateMode }) => {
  const [allGames, setAllGames]     = useState(null);
  const [loading, setLoading]       = useState(true);
  const [giftStatsAll, setGiftStatsAll] = useState(null);

  useEffect(() => {
    const ts = new Date().getTime();
    const fetchGame = fetch('/daily_predictions.json?t=' + ts)
      .then(r => r.ok ? r.json() : null).catch(() => null);
    const fetchGift = fetch('/gift_stats.json?t=' + ts)
      .then(r => r.ok ? r.json() : null).catch(() => null);

    Promise.all([fetchGame, fetchGift]).then(([gameData, giftData]) => {
      if (gameData) setAllGames(gameData);
      if (giftData)  setGiftStatsAll(giftData);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="bg-[#151c28] rounded-xl border border-gray-800 h-80 flex flex-col items-center justify-center">
        <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-3"></div>
        <p className="text-gray-500 font-mono text-xs uppercase tracking-widest animate-pulse">Running Matchups...</p>
      </div>
    );
  }

  const raw = allGames ? allGames[dateMode] : null;
  const games = Array.isArray(raw) ? raw : raw ? [raw] : [];

  if (!games.length) {
    const offsets = { day_before_yesterday:-2, yesterday:-1, today:0, tomorrow:1, day_after_tomorrow:2 };
    const d = new Date();
    d.setDate(d.getDate() + (offsets[dateMode] ?? 0));
    const friendly = d.toLocaleDateString('en-US', { weekday:'long', month:'long', day:'numeric' });
    return (
      <div className="bg-[#151c28] rounded-xl border border-gray-800 h-64 flex flex-col items-center justify-center">
        <p className="text-gray-500 font-mono text-sm uppercase tracking-widest">No scheduled games for {friendly}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {games.map((game, idx) => (
        <SingleMatchupCard
          key={`${game.away?.name}-${game.home?.name}-${idx}`}
          game={game}
          giftStatsAll={giftStatsAll}
          defaultExpanded={idx === 0}
        />
      ))}
    </div>
  );
};

export default NHLMatchupCard;