/** @type {import('next').NextConfig} */
const nextConfig = {
  // Reduce concurrent workers to avoid OOM on Vercel's 2-core/8GB build machines
  experimental: {
    cpus: 1,
  },
};

module.exports = nextConfig;