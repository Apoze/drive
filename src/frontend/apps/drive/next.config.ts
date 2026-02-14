import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const createConfig = (phase: string): NextConfig => {
  return {
    output: "export",
    reactStrictMode: false,
    // Avoid `.next` being mutated by both `next dev` and `next build` (can corrupt
    // the dev server when build runs while dev is running).
    //
    // Do not rely on NODE_ENV (it may be set to "production" even when using `next dev`
    // in some container setups).
    distDir: phase === PHASE_DEVELOPMENT_SERVER ? ".next-dev" : ".next",
  };
};

export default createConfig;
