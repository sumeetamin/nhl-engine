"use client";

import React, { useEffect, useRef, useState } from 'react';
import { publicFile } from '../lib/basePath';

/**
 * The Legends Sports header, so the engine reads as part of the client's site
 * (lgdsanalytics.vercel.app/nhl, 2026-10-16). A copy of his own header
 * (frontend/src/App.jsx and DropdownNavigation.jsx in
 * lgdsbrand/mlb_predictor_engine_v2), with his classes as he wrote them:
 *   1. his logo and LEGENDS SPORTS wordmark with this page's subtitle; the
 *      hamburger below 1024px;
 *   2. his row of sports from 1024px, NHL highlighted, the rest under "More";
 *   3. this page's own tabs (`children`), in his MLB sub-tab style.
 * Every sport link opens his site.
 *
 * KEEP SPORTS IN STEP with his SPORTS_CONFIG (frontend/src/utils/sports_config.js):
 * ACTIVE and BETA sit in the bar, COMING_SOON under "More".
 */

const ORIGIN = 'https://lgdsanalytics.vercel.app';

type Status = 'ACTIVE' | 'BETA' | 'COMING_SOON';
interface Sport { id: string; name: string; icon: string; status: Status }

const SPORTS: Sport[] = [
  { id: 'home', name: 'Home', icon: '🏠', status: 'ACTIVE' },
  { id: 'mlb', name: 'MLB', icon: '⚾', status: 'ACTIVE' },
  { id: 'tennis', name: 'Tennis', icon: '🎾', status: 'ACTIVE' },
  { id: 'nba', name: 'NBA', icon: '🏀', status: 'BETA' },
  { id: 'soccer', name: 'Soccer', icon: '⚽', status: 'COMING_SOON' },
  { id: 'ufc', name: 'UFC', icon: '🥊', status: 'COMING_SOON' },
  { id: 'nfl', name: 'NFL', icon: '🏈', status: 'BETA' },
  { id: 'fantasy', name: 'Fantasy', icon: '🏈', status: 'ACTIVE' },
  { id: 'wnba', name: 'WNBA', icon: '🏀', status: 'BETA' },
  { id: 'nhl', name: 'NHL', icon: '🏒', status: 'BETA' },
  { id: 'cbb', name: 'CBB', icon: '🏀', status: 'COMING_SOON' },
  { id: 'cfb', name: 'CFB', icon: '🏈', status: 'BETA' },
  { id: 'pga', name: 'PGA Tour', icon: '⛳', status: 'COMING_SOON' },
];

// NBA and NHL live at their own paths on his site; the rest are views of his
// app, opened by /?sport=.
const PATHS: Record<string, string> = { home: '/', nba: '/nba', nhl: '/nhl' };
const sportHref = (id: string) => ORIGIN + (PATHS[id] ?? `/?sport=${encodeURIComponent(id)}`);
const infoHref = (dialog: 'about' | 'contact') => `${ORIGIN}/?open=${dialog}`;

const CURRENT = 'nhl';
const WIDTH = 'mx-auto max-w-7xl xl:max-w-[1440px] 2xl:max-w-[1600px]';

/** Open state that closes on Escape or a press anywhere outside `ref`. */
function useClosable(ref: React.RefObject<HTMLElement | null>): [boolean, (open: boolean) => void] {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    const onPress = (event: PointerEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPress);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPress);
    };
  }, [open, ref]);
  return [open, setOpen];
}

function Badge({ status }: { status: Status }) {
  if (status === 'BETA') {
    return <span className="rounded-md border border-cyan-500/30 bg-cyan-950/50 px-1.5 py-0.5 text-[8px] font-black tracking-widest text-cyan-400">BETA</span>;
  }
  if (status === 'COMING_SOON') {
    return <span className="rounded-md border border-slate-800 bg-slate-900/50 px-1.5 py-0.5 text-[8px] font-black tracking-widest text-slate-500">SOON</span>;
  }
  return null;
}

function SportItem({ sport }: { sport: Sport }) {
  const selected = sport.id === CURRENT;
  const soon = sport.status === 'COMING_SOON';
  const className =
    'flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider transition-all duration-200 ' +
    (selected
      ? 'border border-indigo-500/30 border-t-indigo-400/20 bg-indigo-600/20 font-extrabold text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.1)]'
      : 'border border-transparent text-slate-300 hover:bg-slate-900/50 hover:text-slate-100') +
    (soon ? ' opacity-50' : '');
  const body = (
    <>
      <span className="flex items-center gap-3">
        <span className="text-base leading-none">{sport.icon}</span>
        <span>{sport.name}</span>
      </span>
      <Badge status={sport.status} />
    </>
  );
  return soon
    ? <span className={className} aria-disabled="true">{body}</span>
    : <a href={sportHref(sport.id)} className={className}>{body}</a>;
}

function HamburgerMenu() {
  const root = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useClosable(root);
  return (
    <div ref={root} className="relative flex items-center lg:hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label="Toggle navigation menu"
        className="flex items-center justify-center rounded-xl border border-slate-800 bg-slate-900/40 p-2.5 text-slate-400 transition-all duration-300 hover:border-slate-700 hover:bg-slate-800/80 hover:text-slate-200 focus:outline-none active:scale-95"
      >
        <div className="relative h-5 w-5">
          <span className={`absolute left-0 h-0.5 w-5 rounded-full bg-current transition-all duration-300 ${open ? 'top-1/2 -translate-y-1/2 rotate-45' : 'top-1'}`} />
          <span className={`absolute left-0 h-0.5 w-5 rounded-full bg-current transition-all duration-300 ${open ? 'scale-0 opacity-0' : 'top-1/2 -translate-y-1/2'}`} />
          <span className={`absolute left-0 h-0.5 w-5 rounded-full bg-current transition-all duration-300 ${open ? 'top-1/2 -translate-y-1/2 -rotate-45' : 'bottom-1'}`} />
        </div>
      </button>
      {open && (
        <div className="absolute right-0 top-16 z-50 max-h-[80vh] w-72 overflow-y-auto rounded-2xl border border-slate-800 border-t-indigo-500/30 bg-slate-950 p-5 shadow-2xl shadow-black/60">
          <div className="space-y-1">
            <span className="mb-1 block px-2 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Sports Predictors</span>
            {SPORTS.map((sport) => <SportItem key={sport.id} sport={sport} />)}
          </div>
          <div className="my-4 border-t border-slate-900" />
          <div className="space-y-1">
            <span className="mb-1 block px-2 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Information</span>
            {([['about', 'ℹ️', 'About'], ['contact', '✉️', 'Contact']] as const).map(([dialog, icon, label]) => (
              <a key={dialog} href={infoHref(dialog)} className="flex w-full items-center gap-3 rounded-xl border border-transparent px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-slate-300 transition-all hover:bg-slate-900/50 hover:text-slate-100">
                <span className="text-base leading-none">{icon}</span>
                <span>{label}</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MoreMenu() {
  const root = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useClosable(root);
  return (
    <div ref={root} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex items-center gap-1 rounded-lg border border-transparent px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-slate-400 transition-all duration-200 hover:bg-slate-900/40 hover:text-slate-200"
      >
        More <span className={`transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {open && (
        <div className="absolute left-0 top-[calc(100%+8px)] z-50 w-56 space-y-1 rounded-2xl border border-slate-800 border-t-indigo-500/30 bg-slate-950 p-2 shadow-2xl shadow-black/60">
          {SPORTS.filter((s) => s.status === 'COMING_SOON').map((sport) => <SportItem key={sport.id} sport={sport} />)}
        </div>
      )}
    </div>
  );
}

export default function LegendsHeader({ subtitle, children }: { subtitle: string; children?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-50 flex w-full select-none flex-col border-b border-slate-900/80 bg-slate-950/90 shadow-[0_4px_30px_rgba(0,0,0,0.4)] backdrop-blur-md">
      {/* 1. Brand */}
      <div className="w-full border-b border-slate-900/40 px-4 py-3 md:px-8">
        <div className={`${WIDTH} flex items-center justify-between gap-4`}>
          <a href={`${ORIGIN}/`} className="flex min-w-0 flex-shrink-0 flex-col">
            <span className="flex flex-wrap items-center justify-start gap-2 md:gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element -- a fixed-size logo; next/image would need the base path added by hand anyway */}
              <img
                src={publicFile('/legends-logo.png')}
                alt="Legends Sports"
                className="h-9 w-auto object-contain brightness-110 drop-shadow-[0_0_15px_rgba(59,130,246,0.35)] md:h-11 lg:h-12"
              />
              <span className="mx-1 hidden text-xl font-light text-slate-400 sm:inline md:mx-2 md:text-2xl">|</span>
              <span className="mt-0.5 bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-500 bg-clip-text text-lg font-black uppercase tracking-widest text-transparent md:text-xl">
                Legends Sports
              </span>
            </span>
            <span className="mt-0.5 text-[9px] font-bold tracking-tight text-gray-500 md:text-[10px]">{subtitle}</span>
          </a>
          <HamburgerMenu />
        </div>
      </div>

      {/* 2. His sports, desktop */}
      <div className="hidden w-full border-b border-slate-900/20 px-8 py-2 lg:block">
        <div className={`${WIDTH} flex items-center justify-between`}>
          <nav className="flex items-center gap-1 rounded-xl border border-slate-900 bg-slate-900/30 p-0.5" aria-label="Sports">
            {SPORTS.filter((s) => s.status !== 'COMING_SOON').map((sport) => (
              <a
                key={sport.id}
                href={sportHref(sport.id)}
                className={
                  'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[10px] font-black uppercase tracking-widest transition-all duration-200 ' +
                  (sport.id === CURRENT
                    ? 'border border-indigo-500/20 bg-indigo-600/20 font-extrabold text-indigo-400 shadow-[0_0_12px_rgba(99,102,241,0.1)]'
                    : 'border border-transparent text-slate-400 hover:bg-slate-900/40 hover:text-slate-200')
                }
              >
                <span>{sport.icon}</span>
                <span>{sport.name}</span>
                {sport.status === 'BETA' && (
                  <span className="rounded border border-cyan-500/30 bg-cyan-950 px-1 text-[7px] text-cyan-400">BETA</span>
                )}
              </a>
            ))}
            <MoreMenu />
          </nav>
          <div className="flex flex-shrink-0 items-center gap-2">
            {(['about', 'contact'] as const).map((dialog) => (
              <a
                key={dialog}
                href={infoHref(dialog)}
                className="rounded-lg border border-slate-900 px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-slate-400 transition-all hover:bg-slate-900/60 hover:text-slate-200"
              >
                {dialog === 'about' ? 'About' : 'Contact'}
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* 3. This page's tabs */}
      {children && (
        <div className="w-full border-b border-slate-900/20 bg-slate-950/40 px-4 py-2 md:px-8">
          <div className={`${WIDTH} flex items-center gap-2 overflow-x-auto md:gap-1.5`}>{children}</div>
        </div>
      )}
    </header>
  );
}

/** One tab of row 3, his MLB sub-tab style. */
export function HeaderTab({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: string; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={
        'flex flex-shrink-0 items-center gap-1 rounded-lg px-3 py-1.5 text-[10px] font-black uppercase tracking-wider transition-all duration-200 md:px-4 md:tracking-widest ' +
        (active
          ? 'border border-blue-500/30 bg-blue-600/20 font-extrabold text-blue-400 shadow-[0_0_12px_rgba(59,130,246,0.15)]'
          : 'border border-transparent text-slate-400 hover:bg-slate-900/40 hover:text-slate-200')
      }
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  );
}
