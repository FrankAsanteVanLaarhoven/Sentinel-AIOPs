import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // This project lives under /home/favl which has its own lockfile; pin the
  // workspace root so Turbopack resolves this app, not the parent directory.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
