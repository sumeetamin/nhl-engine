/** @type {import('next').NextConfig} */

// The engine is served at lgdsanalytics.vercel.app/nhl, inside the Legends
// Sports site (2026-10-16), the way the football app sits at /football: his
// site forwards /nhl/* here. The one place the prefix is set; the client code
// reads it as NEXT_PUBLIC_BASE_PATH for the files it fetches from public/,
// which basePath does not prefix by itself.
const BASE_PATH = '/nhl';

const nextConfig = {
  basePath: BASE_PATH,
  env: {
    NEXT_PUBLIC_BASE_PATH: BASE_PATH,
  },
  // This host's own root opens the engine rather than a 404.
  async redirects() {
    return [
      { source: '/', destination: BASE_PATH, basePath: false, permanent: false },
    ];
  },
  experimental: {
    cpus: 1,
  },
};

module.exports = nextConfig;
