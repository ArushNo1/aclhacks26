import type { NextConfig } from "next";

const PY_HOST = process.env.GHOST_RACER_BACKEND ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // In dev, rewrite /api, /ws, /stream to the Python uvicorn server so the
  // browser sees same-origin URLs (no CORS, no mixed-content). Production
  // deployments should set GHOST_RACER_BACKEND or sit behind a reverse proxy
  // that terminates the same paths.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${PY_HOST}/api/:path*` },
      { source: "/ws/:path*", destination: `${PY_HOST}/ws/:path*` },
      { source: "/stream/:path*", destination: `${PY_HOST}/stream/:path*` },
    ];
  },
};

export default nextConfig;
