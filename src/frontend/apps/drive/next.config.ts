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
    // pdfjs-dist v5 standard build uses ES2023 static initialization blocks
    // (`static { ... }`) which Safari < 17.4 doesn't support.
    // The legacy build is pre-transpiled but contains its own webpack runtime
    // that clashes with Next.js bundling. Instead we let SWC transpile the
    // clean ESM standard build so it works on all browsers.
    transpilePackages: ["pdfjs-dist"],
  };
};

export default createConfig;
