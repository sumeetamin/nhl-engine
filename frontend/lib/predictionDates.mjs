export function easternDate(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now);
  const part = (type) => parts.find(p => p.type === type).value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

export function dateOptions(today) {
  return [-2, -1, 0, 1, 2].map(offset => {
    const date = new Date(`${today}T12:00:00Z`);
    date.setUTCDate(date.getUTCDate() + offset);
    const fmt = options => date.toLocaleDateString('en-US', { ...options, timeZone: 'UTC' });
    return {
      key: date.toISOString().slice(0, 10),
      label: fmt({ month: 'short', day: 'numeric' }),
      sub: ['2 Days Ago', 'Yesterday', 'Today', 'Tomorrow', fmt({ weekday: 'short' })][offset + 2],
    };
  });
}

// Undated legacy payloads must never be guessed from the viewer's clock.
export function gamesForDate(payload, date) {
  const games = payload?.games_by_date?.[date];
  return Array.isArray(games) ? games : null;
}
