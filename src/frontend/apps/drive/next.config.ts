import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  reactStrictMode: false,
  // Avoid `.next` being mutated by both `next dev` and `next build` (can corrupt
  // the dev server when build runs while dev is running).
  distDir: process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
};

export default nextConfig;
