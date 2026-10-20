"use client";
import React, { useState, useEffect } from 'react';
import { gamesForDate } from '../lib/predictionDates.mjs';
import { publicFile } from '../lib/basePath';

// ── Result Panel (MLB-style) ──────────────────────────────────────────────────
const ResultPanel = ({ result, game }) => {
  if (!result) return null;

  const { away_actual, home_actual, winner, predicted, grades } = result;
  const awayTeam = game.away.name;
  const homeTeam = game.home.name;

  const GradeBox = ({ label, grade }) => {
    if (!grade || grade === 'P') return (
      <div className="flex-1 bg-[#111827] border border-gray-800 rounded-lg p-3 text-center">
        <p className="text-[9px] uppercase tracking-widest text-gray-500 mb-1">{label}</p>
        <p className="text-sm font-black text-gray-500">— PUSH —</p>
      </div>
    );
    const hit = grade === 'W';
    return (
      <div className={`flex-1 border rounded-lg p-3 text-center ${hit ? 'bg-emerald-900/20 border-emerald-800/50' : 'bg-red-900/20 border-red-900/40'}`}>
        <p className="text-[9px] uppercase tracking-widest text-gray-500 mb-1">{label}</p>
        <p className={`text-sm font-black ${hit ? 'text-emerald-400' : 'text-red-400'}`}>
          {hit ? '✅ HIT' : '❌ MISS'}
        </p>
      </div>
    );
  };

  const awayWon = winner === awayTeam;
  const homeWon = winner === homeTeam;

  return (
    <div className="bg-[#0b0f19] border border-gray-700 rounded-xl p-4 space-y-4">

      {/* Actual Score */}
      <div className="text-center">
        <p className="text-[10px] uppercase tracking-widest text-yellow-500 font-bold mb-2">🏆 Actual Final Score</p>
        <div className="flex items-center justify-center space-x-4 bg-[#111827] rounded-xl px-6 py-3 border border-gray-800">
          <div className="text-center">
            <p className="text-[9px] text-gray-500 uppercase mb-1">{awayTeam}</p>
            <p className={`text-4xl font-black ${awayWon ? 'text-emerald-400' : 'text-white'}`}>{away_actual}</p>
          </div>
          <span className="text-gray-600 font-black text-2xl">-</span>
          <div className="text-center">
            <p className="text-[9px] text-gray-500 uppercase mb-1">{homeTeam}</p>
            <p className={`text-4xl font-black ${homeWon ? 'text-emerald-400' : 'text-white'}`}>{home_actual}</p>
          </div>
        </div>
      </div>

      {/* Win prob bar */}
      <div className="flex items-center space-x-2">
        <span className={`text-xs font-black w-10 text-right ${awayWon ? 'text-emerald-400' : 'text-gray-400'}`}>
          {game.away_win_prob ?? (100 - parseFloat(game.prob))}%
        </span>
        <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-red-500 rounded-full"
            style={{ width: `${game.home_win_prob ?? parseFloat(game.prob)}%` }}
          />
        </div>
        <span className={`text-xs font-black w-10 ${homeWon ? 'text-emerald-400' : 'text-gray-400'}`}>
          {game.home_win_prob ?? parseFloat(game.prob)}%
        </span>
      </div>

      {/* Model Accuracy Check */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-3">
        <div className="flex items-center justify-between mb-3 border-b border-gray-800 pb-2">
          <p className="text-[11px] font-black uppercase tracking-widest text-gray-300">🎯 Model Accuracy Check</p>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest">AI Accuracy Telemetry</p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <GradeBox label="Moneyline"  grade={grades?.ml}     />
          <GradeBox label="Spread"     grade={grades?.spread}  />
          <GradeBox label="Total O/U"  grade={grades?.ou}      />
          <GradeBox label="Edge Pick"  grade={grades?.edge}    />
        </div>
      </div>

      {/* Markets Closed */}
      <div className="bg-[#111827] border border-gray-700 rounded-xl p-3 text-center">
        <p className="text-sm font-black text-gray-400">🔒 Markets Closed</p>
        <p className="text-[10px] text-gray-600 uppercase tracking-widest mt-0.5">Game Completed</p>
      </div>
    </div>
  );
};

// ── GIFT Stats Component ───────────────────────────────────────────────────────
const GiftStatTeamCard = ({ team, data }) => {
  const [tab, setTab] = useState('season');

  const pctMap = {
    season: data?.pct_season || 'N/A',
    l5:     data?.pct_l5     || 'N/A',
    l10:    data?.pct_l10    || 'N/A',
  };

  const pct      = pctMap[tab];
  const pctNum   = parseFloat(pct) || 0;
  const pctColor = pctNum >= 65 ? 'text-emerald-400' : pctNum >= 55 ? 'text-yellow-400' : 'text-red-400';
  const streak   = data?.streak || 0;

  return (
    <div className="bg-[#0b0f19] border border-gray-800 rounded-lg p-3 sm:p-4 flex-1">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <img src={`https://a.espncdn.com/i/teamlogos/nhl/500/scoreboard/${team.toLowerCase()}.png`}
            alt={team} className="w-7 h-7 object-contain"
            onError={e => { e.target.style.display='none'; }} />
          <span className="text-sm font-black text-white">{team}</span>
        </div>
        {streak > 0 && (
          <span className="text-[9px] font-black uppercase px-1.5 py-0.5 rounded bg-yellow-900/30 text-yellow-400 border border-yellow-800/30">
            🔥 {streak} streak
          </span>
        )}
      </div>
      <div className="flex space-x-1 bg-[#111827] p-0.5 rounded mb-3">
        {['season','l5','l10'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-1 text-[9px] font-bold uppercase rounded transition-all ${
              tab === t ? 'bg-yellow-600/80 text-white' : 'text-gray-500 hover:text-gray-300'}`}>
            {t === 'season' ? 'Season' : t.toUpperCase()}
          </button>
        ))}
      </div>
      <div className="text-center mb-3">
        <p className={`text-3xl font-black ${pctColor}`}>{pct}</p>
        <p className="text-[9px] uppercase tracking-widest text-gray-600 mt-0.5">GIFT Rate</p>
      </div>
      {data?.record_season && data.record_season !== 'N/A' && (
        <div className="flex justify-between text-[10px] border-t border-gray-800 pt-2 mb-2">
          <span className="text-gray-500">Record</span>
          <span className="font-bold text-white">{data.record_season}</span>
        </div>
      )}
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
  const TeamFP = ({ team, data }) => {
    const [tab, setTab] = useState('season');
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
        <div className="flex items-center space-x-2 mb-3">
          <img src={`https://a.espncdn.com/i/teamlogos/nhl/500/scoreboard/${team.toLowerCase()}.png`}
            alt={team} className="w-6 h-6 object-contain"
            onError={e => { e.target.style.display='none'; }} />
          <span className="text-xs font-black text-white">{team}</span>
        </div>
        <div className="flex space-x-1 bg-[#111827] p-0.5 rounded mb-3">
          {['season','l5','l10'].map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 py-1 text-[9px] font-bold uppercase rounded transition-all ${
                tab === t ? 'bg-blue-600/80 text-white' : 'text-gray-500 hover:text-gray-300'}`}>
              {t === 'season' ? 'Season' : t.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="text-center mb-3">
          <p className={`text-2xl font-black ${color}`}>{pct}</p>
          <p className="text-[9px] uppercase tracking-widest text-gray-600 mt-0.5">1st Period O/U Rate</p>
        </div>
        {data?.record_season && data.record_season !== 'N/A' && (
          <div className="flex justify-between text-[10px] border-t border-gray-800 pt-2 mb-2">
            <span className="text-gray-500">Record</span>
            <span className="font-bold text-white">{data.record_season}</span>
          </div>
        )}
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
        <TeamFP team={awayTeam} data={fpStats?.away} />
        <TeamFP team={homeTeam} data={fpStats?.home} />
      </div>
    </div>
  );
};

// ── Starting goalies ──────────────────────────────────────────────────────────
// Real save % from the NHL's stats API (goalie_stats.py). The colour is judged
// on this season and last together against the league, so one hot week does
// not turn a goalie green; grey means average or too few shots to say.
const GOALIE_TONE = {
  good:    { text: 'text-emerald-400', ring: 'border-emerald-800/50 bg-emerald-900/10' },
  poor:    { text: 'text-red-400',     ring: 'border-red-900/50 bg-red-900/10' },
  average: { text: 'text-gray-200',    ring: 'border-gray-800 bg-[#0b0f19]' },
};

const fmtSv = (v) => (v == null ? '—' : v.toFixed(3).replace(/^0/, ''));

const GoalieSide = ({ team, goalie, alignRight }) => {
  const tone = GOALIE_TONE[goalie?.rating] || GOALIE_TONE.average;
  const confirmed = goalie?.status === 'Confirmed';
  return (
    <div className={`flex-1 min-w-0 border rounded-lg p-2.5 sm:p-3 ${tone.ring} ${alignRight ? 'text-right' : ''}`}>
      <div className={`flex items-center gap-1.5 ${alignRight ? 'justify-end' : ''}`}>
        <span className="text-[9px] font-black text-gray-500">{team}</span>
        <span className={`text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded ${confirmed ? 'bg-emerald-900/40 text-emerald-400' : 'bg-gray-800 text-gray-400'}`}>
          {confirmed ? 'Confirmed' : 'Expected'}
        </span>
      </div>
      <p className="text-xs sm:text-sm font-bold text-white truncate mt-1">{goalie?.name || 'TBD'}</p>
      <p className={`text-xl sm:text-2xl font-black leading-tight ${tone.text}`}>
        {fmtSv(goalie?.sv_pct)}
        <span className="text-[9px] font-bold text-gray-500 ml-1 tracking-widest">SV%</span>
      </p>
      <p className="text-[9px] sm:text-[10px] text-gray-500 font-mono">
        {goalie?.gp ? `${goalie.gp} GP` : 'No games yet'}
        {goalie?.prev_sv_pct != null ? ` · last season ${fmtSv(goalie.prev_sv_pct)}` : ''}
      </p>
    </div>
  );
};

const GoaliesRow = ({ goalies, awayTeam, homeTeam }) => {
  if (!goalies) return null;
  return (
    <div className="mt-3">
      <div className="flex items-center justify-between mb-1.5">
        <p className="text-[9px] sm:text-[10px] uppercase tracking-widest text-gray-400 font-bold">🥅 Starting Goalies</p>
        {goalies.league_sv_pct != null && (
          <p className="text-[9px] text-gray-500 font-mono">League {fmtSv(goalies.league_sv_pct)}</p>
        )}
      </div>
      <div className="flex gap-2">
        <GoalieSide team={awayTeam} goalie={goalies.away} />
        <GoalieSide team={homeTeam} goalie={goalies.home} alignRight />
      </div>
      <p className="text-[8px] sm:text-[9px] text-gray-600 mt-1.5">
        Green better than the league, red worse, judged on this season and last together.
      </p>
    </div>
  );
};

// ── Top plays, above the slate (like the MLB and NFL pages) ───────────────────
const gameAnchor = (game) => `game-${game.away?.name}-${game.home?.name}`;

const TopPlaysStrip = ({ games }) => {
  const plays = games.filter((g) => ['EDGE', 'BIG'].includes(g.tier)).slice(0, 3);
  if (plays.length === 0) return null;
  return (
    <div className="bg-[#151c28] rounded-xl border border-emerald-900/40 p-3 sm:p-4">
      <h3 className="text-sm text-emerald-400 uppercase tracking-widest font-black mb-3 flex items-center">
        <span className="w-1.5 h-4 bg-emerald-500 mr-2 rounded-sm shadow-[0_0_6px_rgba(16,185,129,0.6)]"></span>
        🔥 Top Plays
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {plays.map((game, idx) => (
          <a key={gameAnchor(game)} href={`#${gameAnchor(game)}`}
            className="bg-[#0b0f19] border border-gray-800 hover:border-emerald-700 rounded-lg p-3 transition-colors block">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black text-gray-500">#{idx + 1} · {game.away.name} @ {game.home.name}</span>
              <span className={`text-[9px] font-black px-1.5 py-0.5 rounded ${game.tier === 'BIG' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-blue-500/20 text-blue-300'}`}>{game.tier}</span>
            </div>
            <p className="text-base font-black text-emerald-400 mt-1">{game.details.best_angle.play}</p>
            <p className="text-[10px] text-gray-400 mt-0.5">
              Win prob <span className="text-white font-bold">{game.prob}</span> · Edge <span className="text-emerald-500 font-bold">{game.edge}</span>
            </p>
          </a>
        ))}
      </div>
    </div>
  );
};

// ── Team name lookup ──────────────────────────────────────────────────────────
const getTeamFullName = (abbrev) => {
  const teams = {
    'VGK':'Vegas Golden Knights','COL':'Colorado Avalanche','BOS':'Boston Bruins',
    'TOR':'Toronto Maple Leafs','TBL':'Tampa Bay Lightning','FLA':'Florida Panthers',
    'MTL':'Montreal Canadiens','OTT':'Ottawa Senators','BUF':'Buffalo Sabres',
    'DET':'Detroit Red Wings','CAR':'Carolina Hurricanes','NJD':'New Jersey Devils',
    'NYR':'New York Rangers','WSH':'Washington Capitals','NYI':'New York Islanders',
    'PIT':'Pittsburgh Penguins','PHI':'Philadelphia Flyers','CBJ':'Columbus Blue Jackets',
    'DAL':'Dallas Stars','WPG':'Winnipeg Jets','NSH':'Nashville Predators',
    'STL':'St. Louis Blues','MIN':'Minnesota Wild','ARI':'Arizona Coyotes',
    'CHI':'Chicago Blackhawks','VAN':'Vancouver Canucks','EDM':'Edmonton Oilers',
    'LAK':'Los Angeles Kings','SEA':'Seattle Kraken','CGY':'Calgary Flames',
    'SJS':'San Jose Sharks','ANA':'Anaheim Ducks','UTA':'Utah Hockey Club',
  };
  return teams[abbrev] || abbrev;
};

// ── Single game card ──────────────────────────────────────────────────────────
const SingleMatchupCard = ({ game, giftStatsAll, resultsIndex, defaultExpanded = false }) => {
  const [isExpanded, setIsExpanded]     = useState(defaultExpanded);
  const [activeLogTab, setActiveLogTab] = useState('h2h');

  const predictedWinner = game.details.best_angle.play.split(' ')[0];
  const maxProb         = parseFloat(game.prob);
  const awayTeam        = game.away.name;
  const homeTeam        = game.home.name;

  // Look up result from results_index.json
  const resultKey = `${game.game_date}|${awayTeam}|${homeTeam}`;
  const gameResult   = resultsIndex?.[resultKey] || null;
  const isCompleted  = !!gameResult;

  const getRecord = (logs) => {
    if (!logs?.length) return null;
    const w = logs.filter(l => l.result === 'W').length;
    return { w, l: logs.length - w };
  };

  const awayRecord = getRecord(game.details.recent_logs?.away);
  const homeRecord = getRecord(game.details.recent_logs?.home);
  const h2hRecord  = getRecord(game.details.recent_logs?.h2h);

  return (
    <div id={gameAnchor(game)} className="bg-[#151c28] rounded-xl border border-gray-800 shadow-2xl overflow-hidden transition-all font-sans scroll-mt-4">

      {/* TOP SUMMARY CARD */}
      <div className="p-3 sm:p-6 relative">
        <div className="flex justify-between items-start mb-4 sm:mb-6">

          {/* Away Team */}
          <div className="flex flex-col items-center w-[38%] sm:w-4/12">
            <div className="w-16 h-16 sm:w-24 sm:h-24 bg-[#111827] rounded-full border border-gray-700 flex items-center justify-center mb-2 sm:mb-3 overflow-hidden shadow-inner p-1 sm:p-2">
              <img src={`https://a.espncdn.com/i/teamlogos/nhl/500/scoreboard/${awayTeam.toLowerCase()}.png`}
                alt={awayTeam} className="w-12 h-12 sm:w-16 sm:h-16 object-contain drop-shadow-lg"
                onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='block'; }} />
              <span className="hidden text-lg sm:text-2xl font-black text-gray-400">{awayTeam}</span>
            </div>
            <h2 className="text-[11px] sm:text-lg font-bold text-white text-center leading-tight px-1">{getTeamFullName(awayTeam)}</h2>
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
              {[['OVR', game.away.record_overall, game.home.record_overall],
                ['A/H', game.away.record_split,   game.home.record_split],
                ['L10', game.away.record_l10,     game.home.record_l10]
               ].map(([lbl, awayVal, homeVal]) => (
                <div key={lbl} className="bg-[#111827] border border-gray-800 rounded px-1.5 sm:px-3 py-1 sm:py-1.5 flex items-center w-full shadow-inner">
                  <span className="w-1/3 text-left text-[7px] sm:text-[10px] text-gray-300 font-mono font-bold">{awayVal}</span>
                  <span className="w-1/3 text-center text-[6px] sm:text-[9px] text-gray-500 font-bold uppercase tracking-widest">{lbl}</span>
                  <span className="w-1/3 text-right text-[7px] sm:text-[10px] text-gray-300 font-mono font-bold">{homeVal}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Home Team */}
          <div className="flex flex-col items-center w-[38%] sm:w-4/12">
            <div className="w-16 h-16 sm:w-24 sm:h-24 bg-[#111827] rounded-full border border-gray-700 flex items-center justify-center mb-2 sm:mb-3 overflow-hidden shadow-inner p-1 sm:p-2">
              <img src={`https://a.espncdn.com/i/teamlogos/nhl/500/scoreboard/${homeTeam.toLowerCase()}.png`}
                alt={homeTeam} className="w-12 h-12 sm:w-16 sm:h-16 object-contain drop-shadow-lg"
                onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='block'; }} />
              <span className="hidden text-lg sm:text-2xl font-black text-gray-400">{homeTeam}</span>
            </div>
            <h2 className="text-[11px] sm:text-lg font-bold text-white text-center leading-tight px-1">{getTeamFullName(homeTeam)}</h2>
            <div className="mt-2 sm:mt-3 bg-[#0b0f19] border border-gray-700 px-2 sm:px-6 py-1 sm:py-2 rounded-md text-emerald-400 font-black text-sm sm:text-lg shadow-sm whitespace-nowrap">
              {game.home.ml}
            </div>
          </div>
        </div>

        {/* Result panel (completed games) OR win prob bar (upcoming) */}
        {isCompleted ? (
          <ResultPanel result={gameResult} game={game} />
        ) : (
          <div className="bg-gradient-to-r from-[#0b0f19] via-[#111827] to-[#0b0f19] border border-emerald-900/30 rounded-xl p-3 sm:p-4 shadow-inner flex items-center justify-around mt-3 sm:mt-4">
            <div className="flex flex-col items-center">
              <p className="text-[8px] sm:text-[10px] uppercase tracking-widest text-gray-500 mb-1 font-bold">{awayTeam} Win</p>
              <p className={`text-lg sm:text-2xl font-black ${predictedWinner === awayTeam ? 'text-emerald-400' : 'text-gray-300'}`}>
                {(predictedWinner === awayTeam ? maxProb : 100 - maxProb).toFixed(1)}%
              </p>
            </div>
            <div className="flex flex-col items-center border-l border-r border-gray-800 px-3 sm:px-10">
              <p className="text-[8px] sm:text-[10px] uppercase tracking-widest text-emerald-500/70 mb-1 font-bold">Projected Score</p>
              <div className="flex items-center space-x-2 sm:space-x-3">
                <span className={`text-2xl sm:text-3xl font-black ${predictedWinner === awayTeam ? 'text-emerald-400' : 'text-white'}`}>{game.away.proj}</span>
                <span className="text-gray-600 font-bold text-lg sm:text-xl">-</span>
                <span className={`text-2xl sm:text-3xl font-black ${predictedWinner === homeTeam ? 'text-emerald-400' : 'text-white'}`}>{game.home.proj}</span>
              </div>
            </div>
            <div className="flex flex-col items-center">
              <p className="text-[8px] sm:text-[10px] uppercase tracking-widest text-emerald-500/70 mb-1 font-bold">{homeTeam} Win</p>
              <p className={`text-lg sm:text-2xl font-black ${predictedWinner === homeTeam ? 'text-emerald-400' : 'text-gray-300'}`}>
                {(predictedWinner === homeTeam ? maxProb : 100 - maxProb).toFixed(1)}%
              </p>
            </div>
          </div>
        )}

        <GoaliesRow goalies={game.goalies} awayTeam={awayTeam} homeTeam={homeTeam} />
      </div>

      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full bg-[#1b2436] hover:bg-[#232f46] border-t border-gray-800 py-2.5 sm:py-3.5 text-xs font-bold text-gray-300 uppercase tracking-widest transition-colors flex justify-center items-center shadow-md"
      >
        {isExpanded ? 'Collapse Matchup Details ▲' : 'View Matchup Details ▼'}
      </button>

      {/* EXPANDED DETAILS */}
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
                {['p1','p2','p3'].map((pKey) => {
                  const s = game.details.period_scores[pKey] || "";
                  if (!s.includes(' - ')) return null;
                  const [awayPart, homePart] = s.split(' - ');
                  const at = awayPart.split(' ')[0], as_ = awayPart.split(' ')[1];
                  const ht = homePart.split(' ')[0], hs  = homePart.split(' ')[1];
                  return (
                    <div key={pKey} className="flex justify-between border-b border-gray-800/50 pb-1 last:border-b-0">
                      <span className="uppercase">{pKey} Proj Score:</span>
                      <div className="font-mono text-gray-200">
                        <span className={predictedWinner === at ? "text-emerald-400 font-bold" : ""}>{as_}</span>
                        <span className="text-gray-600 mx-1">-</span>
                        <span className={predictedWinner === ht ? "text-emerald-400 font-bold" : ""}>{hs}</span>
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
                  <span className="text-purple-500 mr-2 mt-0.5 text-xs">▶</span>{note}
                </li>
              ))}
            </ul>
          </div>

          {/* Recent Form */}
          <div className="bg-[#111827] rounded-lg border border-gray-800 p-3 sm:p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-gray-700 mb-4 pb-2 gap-2">
              <h4 className="text-sm text-gray-300 uppercase tracking-widest font-black flex items-center">
                <span className="w-1.5 h-4 bg-orange-500 mr-2 rounded-sm"></span>Recent Form (L10)
              </h4>
              <div className="flex space-x-1 bg-[#0b0f19] p-1 rounded-md border border-gray-800">
                {[['away', awayTeam, awayRecord],['h2h','H2H',h2hRecord],['home',homeTeam,homeRecord]].map(([tab, label, rec]) => (
                  <button key={tab} onClick={() => setActiveLogTab(tab)}
                    className={`flex-1 sm:flex-none px-2 sm:px-3 py-1 text-[10px] font-bold uppercase rounded transition-colors ${
                      activeLogTab === tab
                        ? tab === 'h2h' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-white'
                        : 'text-gray-500 hover:text-gray-300'}`}>
                    {label}{rec && <span className="ml-1 opacity-60">{rec.w}-{rec.l}</span>}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-[10px] text-gray-600 uppercase tracking-widest mb-2 font-mono">
              {activeLogTab === 'h2h' ? `Head-to-Head: ${awayTeam} vs ${homeTeam}`
                : activeLogTab === 'away' ? `${awayTeam} — Last 10 Games`
                : `${homeTeam} — Last 10 Games`}
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

          {/* GIFT + FP Sections */}
          {(() => {
            const aA = awayTeam.toUpperCase(), hA = homeTeam.toUpperCase();
            const awayGift = giftStatsAll?.[aA]?.gift  || game.details.gift_stats?.away;
            const homeGift = giftStatsAll?.[hA]?.gift  || game.details.gift_stats?.home;
            const awayFp   = giftStatsAll?.[aA]?.fp_ou || game.details.fp_stats?.away;
            const homeFp   = giftStatsAll?.[hA]?.fp_ou || game.details.fp_stats?.home;
            return (
              <>
                <GiftStatsSection giftStats={{ away: awayGift, home: homeGift }} awayTeam={awayTeam} homeTeam={homeTeam} />
                <FirstPeriodSection fpStats={{ away: awayFp, home: homeFp }} awayTeam={awayTeam} homeTeam={homeTeam} />
              </>
            );
          })()}

          {/* Legends Predictions */}
          <div className="bg-gradient-to-br from-[#1a2e23] to-[#111827] rounded-lg border border-emerald-900/50 p-4 sm:p-5 shadow-lg relative overflow-hidden">
            <h4 className="text-base sm:text-lg text-emerald-400 uppercase tracking-widest font-black mb-4 border-b border-emerald-900/50 pb-2 flex items-center">
              <span className="w-2 h-5 bg-emerald-500 mr-2 rounded-sm shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
              Legends Sports Predictions
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
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
                  <p className="text-xl sm:text-2xl font-black text-emerald-400">{game.details.best_angle.play}</p>
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

// ── Main NHLMatchupCard ───────────────────────────────────────────────────────
const NHLMatchupCard = ({ selectedDate, payload, loading }) => {
  const [giftStatsAll, setGiftStatsAll] = useState(null);
  const [resultsIndex, setResultsIndex] = useState(null);

  useEffect(() => {
    const ts = new Date().getTime();
    Promise.all([
      fetch(publicFile('/gift_stats.json?t=')         + ts).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(publicFile('/results_index.json?t=')      + ts).then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([giftData, resultsData]) => {
      if (giftData)    setGiftStatsAll(giftData);
      if (resultsData) setResultsIndex(resultsData);
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

  const games = gamesForDate(payload, selectedDate);
  const friendly = selectedDate ? new Date(`${selectedDate}T12:00:00Z`).toLocaleDateString(
    'en-US', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC' }
  ) : 'the selected date';

  if (!games?.length) {
    return (
      <div className="bg-[#151c28] rounded-xl border border-gray-800 h-64 flex flex-col items-center justify-center">
        <p className="text-gray-500 font-mono text-sm uppercase tracking-widest">{games === null ? `Predictions unavailable for ${friendly}. Waiting for an update.` : `No scheduled games for ${friendly}`} </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <TopPlaysStrip games={games} />
      {games.map((game, idx) => (
        <SingleMatchupCard
          key={`${selectedDate}-${game.away?.name}-${game.home?.name}-${idx}`}
          game={game}
          giftStatsAll={giftStatsAll}
          resultsIndex={resultsIndex}
          defaultExpanded={false}
        />
      ))}
    </div>
  );
};

export default NHLMatchupCard;
