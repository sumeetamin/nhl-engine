// The prefix the app is served under (next.config.js). Files in public/ are
// served under it too, but fetch() does not add it, so every fetch of one goes
// through here.
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? '';

export function publicFile(path: string): string {
  return `${BASE_PATH}${path}`;
}
