import type { NextConfig } from "next";
import { readServerEnv } from "./src/env";
import { STATIC_SECURITY_HEADERS } from "./src/lib/security-headers";

const env = readServerEnv();

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${env.LEGIVEL_API_URL}/api/:path*` },
      { source: "/health", destination: `${env.LEGIVEL_API_URL}/health` },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: STATIC_SECURITY_HEADERS }];
  },
};

export default nextConfig;
