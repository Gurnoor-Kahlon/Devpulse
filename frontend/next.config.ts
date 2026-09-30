import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  agentRules: false,
  output:
    process.env.DEVPULSE_CONTAINER_BUILD === "1" ? "standalone" : undefined,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination:
          process.env.DEVPULSE_CONTAINER_BUILD === "1"
            ? "http://api:8000/api/v1/:path*"
            : "http://127.0.0.1:8000/api/v1/:path*",
      },
    ];
  },
  turbopack: {
    root: path.resolve(import.meta.dirname),
  },
};

export default nextConfig;
