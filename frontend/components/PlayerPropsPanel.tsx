"use client";

import { useEffect, useMemo, useState } from "react";
import { publicFile } from "../lib/basePath";

type Split = { hits?: number; total?: number; hit_rate?: number | null };
type HistorySplits = { l5?: Split; l10?: Split; h2h?: Split; season?: Split };
type HitGame = { date: string; opponent: string; value: number; hit: boolean | null };
type PlayerProp = {
  prop_id: string;
  game_id: string;
  game_date: string;
  commence_time?: string;
  game_label?: string;
  player_id?: number | string;
  player: string;
  team: string;
  opponent: string;
  position?: string;
  market: string;
  market_label?: string;
  line?: number | null;
  over_odds?: number | null;
  under_odds?: number | null;
  side?: "over" | "under";
  price?: number | null;
  probability?: number | null;
  projection?: number | null;
  window?: "l5" | "l10";
  best_book?: string | null;
  books?: Array<{ book: string; over?: number | null; under?: number | null }>;
  confidence?: number | null;
  edge_pct?: number | null;
  over_probability?: number | null;
  under_probability?: number | null;
  push_probability?: number | null;
  defense_rank?: number | null;
  defense_allowed?: number | null;
  history?: HistorySplits;
  hit_chart?: HitGame[];
  toi_minutes?: number | null;
  team_pace?: number | null;
  opponent_pace?: number | null;
  goalie_name?: string | null;
  goalie_status?: "confirmed" | "projected" | "unknown" | string;
  availability_status?: string;
};
type Feed = {
  version?: number;
  updated_at?: string | null;
  odds_snapshot_at?: string | null;
  source_status?: string;
  games?: Array<{ game_id: string; game_label: string; game_date: string; commence_time?: string }>;
  props?: PlayerProp[];
  cheat_sheets?: PlayerProp[];
  top_plays?: PlayerProp[];
  tracker?: Array<{ prop_id: string; result: "hit" | "miss" | "push" | "void" | "pending" }>;
};
type Props = { view: "props" | "cheat" };

const PAGE_SIZE = 50;
const MARKETS = [
  "All props",
  "Shots on Goal",
  "Points",
  "Assists",
  "Goals",
  "Goalie Saves",
  "Team Shots",
];
const EMPTY: Feed = { games: [], props: [], cheat_sheets: [], tracker: [] };

function percent(value?: number | null) {
  return value == null || !Number.isFinite(value) ? "—" : `${Math.round(value)}%`;
}
function odds(value?: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  return value > 0 ? `+${value}` : String(value);
}
function record(split?: Split) {
  if (!split || split.total == null || split.total === 0) return "—";
  return `${percent(split.hit_rate)} ${split.hits ?? 0}/${split.total}`;
}
function localDate(value?: string | null) {
  if (!value) return "Not updated yet";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not updated yet" : date.toLocaleString("en-US", {
    timeZone: "America/New_York", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  }) + " ET";
}

function PropTable({ rows, onAdd, saved }: {
  rows: PlayerProp[];
  onAdd: (row: PlayerProp) => void;
  saved: Set<string>;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const lastPage = Math.ceil(rows.length / PAGE_SIZE) - 1;
  const currentPage = Math.min(page, Math.max(lastPage, 0));
  const first = currentPage * PAGE_SIZE;
  if (rows.length === 0) {
    return <div className="rounded-2xl border border-slate-800 bg-[#111827] px-5 py-14 text-center text-sm text-slate-400">No player props are available for these filters yet. The feed will show projections when the scheduled update has valid slate data.</div>;
  }
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800 bg-[#101722]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] border-collapse text-left text-xs">
          <thead className="bg-slate-900/80 text-[10px] uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-3 py-3">+</th><th className="px-3 py-3">Player / prop</th>
              <th className="px-3 py-3">Confidence</th><th className="px-3 py-3">Odds</th>
              <th className="px-3 py-3">L5</th><th className="px-3 py-3">L10</th>
              <th className="px-3 py-3">H2H</th><th className="px-3 py-3">Season</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80">
            {rows.slice(first, first + PAGE_SIZE).map((row) => {
              const open = expanded === row.prop_id;
              const savedRow = saved.has(row.prop_id);
              return (
                <FragmentRow key={row.prop_id} row={row} open={open} saved={savedRow}
                  onToggle={() => setExpanded(open ? null : row.prop_id)} onAdd={() => onAdd(row)} />
              );
            })}
          </tbody>
        </table>
      </div>
      {lastPage > 0 && (
        <nav aria-label="Player props pages" className="flex items-center justify-between gap-3 border-t border-slate-800 px-3 py-2 text-xs text-slate-300">
          <button type="button" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)} className="px-2 py-1 disabled:opacity-40">Previous</button>
          <span aria-live="polite">{first + 1}–{Math.min(first + PAGE_SIZE, rows.length)} of {rows.length}</span>
          <button type="button" disabled={currentPage === lastPage} onClick={() => setPage(currentPage + 1)} className="px-2 py-1 disabled:opacity-40">Next</button>
        </nav>
      )}
    </div>
  );
}


function HitRateChart({ row }: { row: PlayerProp }) {
  const games = row.hit_chart || [];
  if (!games.length) return <div className="mt-4 rounded-lg bg-slate-900 p-3 text-xs text-slate-400">Recent game results are unavailable for this line.</div>;
  const maximum = Math.max(row.line ?? 0, ...games.map((game) => game.value), 1);
  return (
    <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-xs font-bold text-white">Recent hit rate · {row.side === "under" ? "Under" : "Over"} {row.line}</h4>
        <span className="text-[10px] text-slate-400">{games.filter((game) => game.hit !== null).length} settled games</span>
      </div>
      <div role="img" aria-label={`Recent ${games.length} games against ${row.side} ${row.line} ${row.market_label}`} className="flex h-32 items-end gap-2 border-b border-dashed border-slate-600 px-1">
        {games.slice().reverse().map((game, index) => {
          const height = Math.max(8, Math.round(game.value / maximum * 100));
          const color = game.hit === null ? "bg-slate-500" : game.hit ? "bg-emerald-400" : "bg-rose-400";
          return <div key={`${game.date}-${game.opponent}-${index}`} title={`${game.date} vs ${game.opponent}: ${game.value} (${game.hit === null ? "push" : game.hit ? "hit" : "miss"})`} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1">
            <span className="text-[10px] font-semibold text-slate-200">{game.value}</span>
            <span className={`w-full max-w-8 rounded-t ${color}`} style={{ height: `${height}%` }} />
            <span className="truncate text-[9px] text-slate-400">{game.opponent || game.date.slice(5)}</span>
          </div>;
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-slate-400">
        <span>Stat result</span><span>Line {row.line}</span><span className="text-emerald-300">Hit</span><span className="text-rose-300">Miss</span><span>Push excluded from hit rate</span>
      </div>
    </div>
  );
}

function FragmentRow({ row, open, saved, onToggle, onAdd }: {
  row: PlayerProp; open: boolean; saved: boolean; onToggle: () => void; onAdd: () => void;
}) {
  const direction = row.side === "under" ? "Under" : row.side === "over" ? "Over" : "Both";
  const defensiveRank = row.defense_rank == null ? null : Math.round(row.defense_rank);
  const playerHeadshot = row.player_id == null ? null : `https://assets.nhle.com/mugs/nhl/20262027/${row.player_id}.png`;
  const books = row.books?.map((book) => `${book.book}: O ${odds(book.over)} / U ${odds(book.under)}`).join(" · ");
  return (
    <>
      <tr className="cursor-pointer text-slate-200 hover:bg-slate-800/40" onClick={onToggle}>
        <td className="px-3 py-3">
          <button type="button" aria-label={saved ? "Remove from sheet" : "Add to sheet"} onClick={(event) => { event.stopPropagation(); onAdd(); }}
            className={`h-7 w-7 rounded-md border text-base font-bold ${saved ? "border-indigo-400 bg-indigo-500/20 text-indigo-300" : "border-slate-700 text-slate-300 hover:border-indigo-400"}`}>
            {saved ? "✓" : "+"}
          </button>
        </td>
        <td className="px-3 py-3">
          <button type="button" className="text-left" aria-expanded={open}>
            <span className="flex items-center gap-2 font-bold text-white">{playerHeadshot && <img src={playerHeadshot} alt="" loading="lazy" className="h-9 w-9 rounded-full bg-slate-800 object-cover" />} {row.player}</span>
            {defensiveRank != null && <span className="mt-1 inline-flex rounded-md border border-slate-700 bg-slate-900 px-2 py-0.5 text-[10px] font-bold text-cyan-200">DEF vs {row.position || "POS"} #{defensiveRank}</span>}
            <span className="mt-1 block text-[10px] text-slate-400">{row.team} vs {row.opponent}</span><span className="mt-1 block text-sm font-extrabold uppercase text-white">{row.line == null ? (row.market_label || row.market) : `${direction} ${row.line} ${row.market_label || row.market}`}</span>
            {row.projection != null && <span className="block text-xs text-cyan-300">Model projection {row.projection.toFixed(2)}</span>}
          </button>
        </td>
        <td className="px-3 py-3 font-semibold text-cyan-300">{percent(row.confidence)}</td>
        <td className="px-3 py-3">{row.best_book && row.price != null ? <span className="font-extrabold text-white"><span className="text-[10px] uppercase tracking-wide text-cyan-300">{row.best_book === "fanduel" ? "FanDuel" : row.best_book === "draftkings" ? "DraftKings" : row.best_book}</span><br />{row.side === "under" ? "U" : "O"} {odds(row.price)}</span> : <span className="text-slate-500">—</span>}</td>
        <td className="px-3 py-3">{record(row.history?.l5)}</td>
        <td className="px-3 py-3">{record(row.history?.l10)}</td>
        <td className="px-3 py-3">{record(row.history?.h2h)}</td>
        <td className="px-3 py-3">{record(row.history?.season)}</td>
      </tr>
      {open && (
        <tr className="bg-slate-950/70">
          <td colSpan={8} className="px-5 py-4">
            <div className="grid gap-3 text-[11px] text-slate-300 sm:grid-cols-2 lg:grid-cols-4">
              <div><span className="text-slate-500">Model projection</span><p className="mt-1 text-base font-bold text-white">{row.projection == null ? "—" : row.projection.toFixed(2)} projected · line {row.line ?? "—"}</p></div>
              <div><span className="text-slate-500">Model probabilities</span><p className="mt-1">{row.side === "under" ? "Under" : "Over"} {percent(row.probability ?? (row.side === "under" ? row.under_probability : row.over_probability))}{row.side ? "" : ` · Under ${percent(row.under_probability)}`} · Push {percent(row.push_probability)}</p></div>
              <div><span className="text-slate-500">Edge vs book</span><p className="mt-1">{row.edge_pct == null ? "Unavailable" : `${row.edge_pct.toFixed(1)} percentage points`}</p></div>
              <div><span className="text-slate-500">Defense vs position</span><p className="mt-1">{row.defense_rank == null ? "Rank unavailable" : `DEF vs ${row.position || "POS"} #${Math.round(row.defense_rank)}`} {row.defense_allowed == null ? "" : `· ${row.defense_allowed.toFixed(1)} allowed`}</p></div>
              <div><span className="text-slate-500">Recent TOI</span><p className="mt-1">{row.toi_minutes == null ? "Unavailable" : `${row.toi_minutes.toFixed(1)} min`}</p></div>
              <div><span className="text-slate-500">Team pace</span><p className="mt-1">{row.team_pace == null ? "Unavailable" : `${row.team_pace.toFixed(1)} SOG/game`} {row.opponent_pace == null ? "" : `· opponent ${row.opponent_pace.toFixed(1)}`}</p></div>
              <div><span className="text-slate-500">Goalie</span><p className="mt-1">{row.goalie_name || "Not announced"}{row.goalie_status ? ` · ${row.goalie_status}` : ""}</p></div>
              <div><span className="text-slate-500">Availability</span><p className="mt-1">{row.availability_status || "Not confirmed"}</p></div>
              <div><span className="text-slate-500">Sportsbook prices</span><p className="mt-1">{books || "No permitted-book prices in the latest odds snapshot."}</p></div>
            </div>
          </td>
        </tr>
      )}
      {open && (
        <tr className="bg-slate-950/70">
          <td colSpan={8} className="px-5 pb-5">
            <HitRateChart row={row} />
          </td>
        </tr>
      )}
    </>
  );
}

export default function PlayerPropsPanel({ view }: Props) {
  const [feed, setFeed] = useState<Feed>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [search, setSearch] = useState("");
  const [selectedGame, setSelectedGame] = useState("all");
  const [market, setMarket] = useState("All props");
  const [side, setSide] = useState("both");
  const [windowFilter, setWindowFilter] = useState("all");
  const [sort, setSort] = useState("confidence");
  const [savedIds, setSavedIds] = useState<string[]>([]);
  const [savedProps, setSavedProps] = useState<PlayerProp[]>([]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    fetch(publicFile("/player_props.json?v=") + Date.now(), { cache: "no-store", signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("Player props feed unavailable"); return response.json(); })
      .then((data: Feed) => {
        if (!Array.isArray(data?.props)) throw new Error("Invalid player props feed");
        if (active) setFeed({ ...EMPTY, ...data });
      })
      .catch(() => { if (active) setLoadError(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [attempt]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("nhl-player-props-sheet");
      if (stored) {
        const decoded: unknown = JSON.parse(stored);
        if (Array.isArray(decoded)) {
          const oldIds = decoded.filter((value): value is string => typeof value === "string");
          setSavedIds(oldIds);
        } else if (decoded && typeof decoded === "object" && "items" in decoded && Array.isArray((decoded as { items: unknown[] }).items)) {
          const items = (decoded as { items: PlayerProp[] }).items.filter((row) => row && typeof row.prop_id === "string");
          setSavedProps(items);
          setSavedIds(items.map((row) => row.prop_id));
        }
      }
    } catch { /* Ignore unavailable or malformed browser storage. */ }
  }, []);

  const rows = useMemo(() => {
    const source = view === "cheat" ? feed.cheat_sheets || [] : feed.props || [];
    const filtered = source.filter((row) => {
      const matchesSearch = `${row.player} ${row.team} ${row.opponent}`.toLowerCase().includes(search.toLowerCase());
      const matchesGame = selectedGame === "all" || row.game_id === selectedGame;
      const matchesMarket = market === "All props" || row.market_label === market ||
        (market === "Shots on Goal" && row.market === "player_shots_on_goal") ||
        (market === "Points" && row.market === "player_points") ||
        (market === "Assists" && row.market === "player_assists") ||
        (market === "Goals" && row.market === "player_goals") ||
        (market === "Goalie Saves" && row.market === "goalie_saves") ||
        (market === "Team Shots" && row.market === "team_shots_on_goal");
      const matchesSide = side === "both" || row.side === side;
      const matchesWindow = view !== "cheat" || windowFilter === "all" || row.window === windowFilter;
      return matchesSearch && matchesGame && matchesMarket && matchesSide && matchesWindow;
    });
    return filtered.sort((a, b) => {
      if (sort === "projection") return (b.projection ?? -Infinity) - (a.projection ?? -Infinity);
      if (sort === "edge") return (b.edge_pct ?? -Infinity) - (a.edge_pct ?? -Infinity);
      if (sort === "defense") return (a.defense_rank ?? Infinity) - (b.defense_rank ?? Infinity);
      return (b.confidence ?? -Infinity) - (a.confidence ?? -Infinity);
    });
  }, [feed, view, search, selectedGame, market, side, windowFilter, sort]);

  const persistSheet = (items: PlayerProp[]) => {
    setSavedProps(items);
    const ids = items.map((item) => item.prop_id);
    setSavedIds(ids);
    try { window.localStorage.setItem("nhl-player-props-sheet", JSON.stringify({ version: 1, items })); } catch { /* Storage is optional. */ }
  };
  const addToSheet = (row: PlayerProp) => {
    const current = savedProps.length ? savedProps : savedIds
      .map((id) => (feed.props || []).find((item) => item.prop_id === id))
      .filter((item): item is PlayerProp => Boolean(item));
    persistSheet(savedIds.includes(row.prop_id)
      ? current.filter((item) => item.prop_id !== row.prop_id)
      : [...current, row]);
  };
  const removeFromSheet = (id: string) => {
    const current = savedProps.length ? savedProps : savedIds
      .map((savedId) => (feed.props || []).find((item) => item.prop_id === savedId))
      .filter((item): item is PlayerProp => Boolean(item));
    persistSheet(current.filter((item) => item.prop_id !== id));
  };

  const tableKey = JSON.stringify([view, search, selectedGame, market, side, windowFilter, sort]);
  const propRows = feed.props || [];
  const pricedPropCount = propRows.filter((row) => row.line != null && row.best_book != null).length;
  const tracker = feed.tracker || [];
  const tracked = tracker.filter((item) => item.result === "hit" || item.result === "miss");
  const hits = tracked.filter((item) => item.result === "hit").length;
  const hitRate = tracked.length ? Math.round(100 * hits / tracked.length) : null;

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-black uppercase tracking-wide text-white">{view === "cheat" ? "Trends & Cheat Sheets" : "NHL Player Props"}</h2>
          <p className="mt-1 text-xs text-slate-400">Feed updated {localDate(feed.updated_at)} · odds snapshot {localDate(feed.odds_snapshot_at)}</p>
          {view === "props" && !loading && propRows.length > 0 && pricedPropCount < propRows.length && (
            <p role="status" className="mt-2 max-w-2xl rounded-lg border border-amber-900/60 bg-amber-950/20 px-3 py-2 text-xs text-amber-200">
              {pricedPropCount === 0
                ? "Projections are loaded, but the latest odds snapshot has no approved-book player-prop lines. Odds, confidence, edge, and line-based hit rates will appear when matching lines are available."
                : "Approved-book lines are available for " + pricedPropCount + " of " + propRows.length + " projected rows. Other rows do not have a matching line in the latest snapshot."}
            </p>
          )}
        </div>
        {view === "props" && <div className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-[11px] text-slate-300">Top-plays tracker: {hitRate == null ? "No graded props yet" : `${hits}/${tracked.length} hits · ${hitRate}%`}</div>}
      </div>

      {view === "props" && (feed.top_plays || []).length > 0 && (
        <div className="rounded-2xl border border-emerald-900/50 bg-emerald-950/10 p-4">
          <h3 className="mb-3 text-xs font-black uppercase tracking-wider text-emerald-300">Top model edges</h3>
          <div className="grid gap-2 md:grid-cols-2">
            {(feed.top_plays || []).slice(0, 6).map((row) => (
              <div key={row.prop_id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-950/60 px-3 py-2 text-xs">
                <span className="min-w-0 truncate text-white">{row.player} · {row.market_label} {row.side} {row.line}</span>
                <span className="shrink-0 font-bold text-emerald-300">{row.edge_pct == null ? "—" : `+${row.edge_pct.toFixed(1)} pp`}</span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[10px] text-slate-500">Edge is model probability minus the best available book’s no-vig probability. Model probabilities are not yet calibrated.</p>
        </div>
      )}

      {view === "props" ? (
        <div className="grid gap-2 rounded-2xl border border-slate-800 bg-[#111827] p-3 sm:grid-cols-2 lg:grid-cols-5">
          <label className="text-[10px] uppercase tracking-wide text-slate-500">Search players<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Player or team" className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white" /></label>
          <label className="text-[10px] uppercase tracking-wide text-slate-500">Games<select value={selectedGame} onChange={(event) => setSelectedGame(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"><option value="all">All games</option>{(feed.games || []).map((game) => <option key={game.game_id} value={game.game_id}>{game.game_label}</option>)}</select></label>
          <label className="text-[10px] uppercase tracking-wide text-slate-500">Props<select value={market} onChange={(event) => setMarket(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white">{MARKETS.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="text-[10px] uppercase tracking-wide text-slate-500">Over / Under<select value={side} onChange={(event) => setSide(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"><option value="both">Both</option><option value="over">Over</option><option value="under">Under</option></select></label>
          <label className="text-[10px] uppercase tracking-wide text-slate-500">Sort by<select value={sort} onChange={(event) => setSort(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"><option value="confidence">Confidence</option><option value="projection">Highest projection</option><option value="edge">Edge</option><option value="defense">Defense rank</option></select></label>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-slate-800 bg-[#111827] p-3 text-xs text-slate-300">
          <label>Search <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Player or team" className="ml-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white" /></label>
          <label>Market <select value={market} onChange={(event) => setMarket(event.target.value)} className="ml-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white">{MARKETS.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>Window <select value={windowFilter} onChange={(event) => setWindowFilter(event.target.value)} className="ml-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"><option value="all">L5 or L10</option><option value="l5">L5</option><option value="l10">L10</option></select></label>
          <span className="text-slate-500">Showing feed-qualified 80% and 100% hit-rate trends only.</span>
        </div>
      )}

      {loading ? <div className="rounded-2xl border border-slate-800 bg-[#111827] p-10 text-center text-sm text-slate-400">Loading player props…</div> : loadError ? (
        <div role="alert" className="rounded-2xl border border-slate-800 bg-[#111827] p-6 text-center text-sm text-slate-300">
          Player props could not load. <button type="button" className="text-cyan-300 underline" onClick={() => { setLoading(true); setLoadError(false); setAttempt(value => value + 1); }}>Try again</button>
        </div>
      ) :
        view === "props" ? <PropTable key={tableKey} rows={rows} onAdd={addToSheet} saved={new Set(savedIds)} /> :
        <div className="space-y-3">
          {rows.length === 0 ? <div className="rounded-2xl border border-slate-800 bg-[#111827] p-10 text-center text-sm text-slate-400">No 80% or 100% hit-rate trends are available for these filters yet.</div> :
            <PropTable key={tableKey} rows={rows} onAdd={addToSheet} saved={new Set(savedIds)} />}
        </div>}

      {view === "props" && savedIds.length > 0 && (
        <div className="rounded-2xl border border-indigo-900/60 bg-indigo-950/20 p-3">
          <h3 className="mb-2 text-xs font-black uppercase tracking-wider text-indigo-200">My sheet · {savedIds.length} saved</h3>
          <div className="space-y-2">
            {savedIds.map((id) => {
              const row = savedProps.find((item) => item.prop_id === id) || (feed.props || []).find((item) => item.prop_id === id);
              return <div key={id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-950/50 px-3 py-2 text-xs text-slate-200">
                <span>{row ? `${row.player} · ${row.market_label || row.market} ${row.side || ""} ${row.line ?? ""}` : id}</span>
                <button type="button" onClick={() => removeFromSheet(id)} className="text-indigo-300 hover:text-white">Remove</button>
              </div>;
            })}
          </div>
          <p className="mt-2 text-[10px] text-slate-500">Saved in this browser only.</p>
        </div>
      )}
      {feed.source_status && <p className="text-center text-[10px] text-slate-500">{feed.source_status}</p>}
    </section>
  );
}