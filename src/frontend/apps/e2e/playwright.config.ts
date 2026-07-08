import { defineConfig, devices } from "@playwright/test";
import fs from "fs";
import { getE2EBaseURL } from "./e2e-origins";

const PORT = process.env.PORT || 3000;
const requestedWorkers = Math.max(
  1,
  Number.parseInt(process.env.PLAYWRIGHT_WORKERS || "1", 10) || 1,
);
const allowCiWorkerOverride =
  process.env.PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE === "1";
const configuredWorkers =
  process.env.CI && !allowCiWorkerOverride ? 1 : requestedWorkers;
const generatedRunId =
  process.env.E2E_RUN_ID ||
  `pw-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}-${process.pid}`;

process.env.E2E_RUN_ID = generatedRunId;

const baseURL = getE2EBaseURL();
const externalWeb = process.env.E2E_EXTERNAL_WEB === "1";
const networkMode = process.env.E2E_NETWORK_MODE || "manual";
const treatInsecureOriginAsSecure =
  baseURL.startsWith("http://") && !baseURL.startsWith("http://localhost")
    ? baseURL
    : null;

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  // Timeout per test
  timeout: 30 * 1000,
  testDir: "./__tests__",
  outputDir: "./test-results",
  metadata: {
    e2eBaselineMode: "independent-one-stack",
    legacyControlSpec: "__tests__/app-drive/e2e-ready-smoke.spec.ts",
    bootstrapMigrationPhase: "phase-12",
    e2eRunId: generatedRunId,
    requestedWorkers,
    configuredWorkers,
    allowCiWorkerOverride,
  },

  fullyParallel: false,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  maxFailures: process.env.CI ? 3 : 0,
  /* Opt out of parallel tests on CI. */
  workers: configuredWorkers,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: [["html", { outputFolder: "./playwright-report", open: "never" }]],
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  snapshotPathTemplate: '{snapshotDir}/{arg}{-projectName}{ext}',
  use: {
    baseURL,
    viewport: { width: 1280, height: 720 },

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: "on-first-retry",
    video: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  webServer: externalWeb
    ? networkMode === "compose"
      ? {
          command: "node ./scripts/loopback-proxies.js",
          url: baseURL,
          timeout: 30 * 1000,
          reuseExistingServer: true,
        }
      : undefined
    : {
        command: !process.env.CI ? `cd ../drive && yarn dev --port ${PORT}` : "",
        url: baseURL,
        timeout: 120 * 1000,
        reuseExistingServer: true,
      },
  /* Configure projects for major browsers */
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        locale: "en-US",
        timezoneId: "Europe/Paris",
        launchOptions: {
          ...(process.env.PLAYWRIGHT_USE_SYSTEM_CHROMIUM
            ? {
                executablePath:
                  (fs.existsSync("/usr/bin/chromium-browser") &&
                    "/usr/bin/chromium-browser") ||
                  (fs.existsSync("/usr/bin/chromium") && "/usr/bin/chromium") ||
                  undefined,
              }
            : {}),
          args: [
            ...(treatInsecureOriginAsSecure
              ? [
                  `--unsafely-treat-insecure-origin-as-secure=${treatInsecureOriginAsSecure}`,
                ]
              : []),
          ],
        },
        contextOptions: {
          permissions: ["clipboard-read", "clipboard-write"],
        },
      },
    },
    {
      name: "webkit",
      use: {
        ...devices["Desktop Safari"],
        locale: "en-US",
        timezoneId: "Europe/Paris",
        contextOptions: {
          permissions: ["clipboard-read"],
        },
      },
    },
    {
      name: "firefox",
      use: {
        ...devices["Desktop Firefox"],
        locale: "en-US",
        timezoneId: "Europe/Paris",
        launchOptions: {
          firefoxUserPrefs: {
            "dom.events.asyncClipboard.readText": true,
            "dom.events.testing.asyncClipboard": true,
          },
        },
      },
    },
  ],
});
