/** @type {import('next').NextConfig} */
const nextConfig = {
  // Reduce concurrent workers to avoid OOM on Vercel's 2-core/8GB build machines
  experimental: {
    cpus: 1,
  },
  // Increase memory for the build process
  env: {
    NODE_OPTIONS: '--max_old_space_size=4096',
  },
};

module.exports = nextConfig;