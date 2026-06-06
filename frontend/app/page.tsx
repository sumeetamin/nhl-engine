// app/page.tsx — SERVER COMPONENT (no "use client")
// force-dynamic only works in server components — this wrapper makes it stick
export const dynamic = 'force-dynamic';

import Dashboard from './Dashboard';

export default function Page() {
  return <Dashboard />;
}