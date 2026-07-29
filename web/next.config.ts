import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep recently visited dynamic tabs warm so back/tab switches feel instant.
  experimental: {
    staleTimes: {
      dynamic: 30,
      static: 180,
    },
  },
};

export default nextConfig;
