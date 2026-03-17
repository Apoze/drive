import { expect, Page } from "@playwright/test";
import { exec } from "child_process";
import http from "http";
import path from "path";
import { URL } from "url";
import type { WorkerActorFixture } from "./fixtures/types";
// We need to use __dirname to get the root path of the project
// because Playwright runs tests in a different directory from the root
// by default.
const ROOT_PATH = path.join(__dirname, "/../../../../../..");
const CLEAR_DB_TARGET = "clear-db-e2e";
const DEFAULT_API_ORIGIN = "http://192.168.10.123:8071";
export const LEGACY_E2E_CLEAR_DB_PATH = "/api/v1.0/e2e/clear-db/";
export const LEGACY_E2E_USER_AUTH_PATH = "/api/v1.0/e2e/user-auth/";
export const LEGACY_E2E_READYNESS_SPEC =
  "__tests__/app-drive/e2e-ready-smoke.spec.ts";
export const E2E_BOOTSTRAP_SESSION_PATH = "/api/v1.0/e2e/bootstrap-session/";
export const E2E_BOOTSTRAP_SCENARIO_PATH = "/api/v1.0/e2e/bootstrap-scenario/";
export const E2E_CLEANUP_SCOPE_PATH = "/api/v1.0/e2e/cleanup-scope/";
const RETRYABLE_REQUEST_ERROR_PATTERNS = [
  /socket hang up/i,
  /ECONNRESET/i,
  /ECONNREFUSED/i,
  /ETIMEDOUT/i,
  /fetch failed/i,
];
const REQUEST_RETRY_DELAYS_MS = [150, 300];

export const getS2SHeaders = () => {
  const token = process.env.E2E_S2S_TOKEN;
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
};

export const getE2EApiOrigin = () => {
  return process.env.E2E_API_ORIGIN || DEFAULT_API_ORIGIN;
};

export const keepE2EScopes = () => {
  return process.env.E2E_KEEP_SCOPES === "1";
};

const postJson = async (url: string, body: unknown) => {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getS2SHeaders(),
    },
    body: JSON.stringify(body),
  });
  return res;
};

const parseJsonResponse = async <T>(res: Response, label: string): Promise<T> => {
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${label} failed with status ${res.status}: ${text}`);
  }
  return JSON.parse(text) as T;
};

const isRetryableRequestError = (error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  return RETRYABLE_REQUEST_ERROR_PATTERNS.some((pattern) => pattern.test(message));
};

const sleep = async (delayMs: number) => {
  await new Promise((resolve) => setTimeout(resolve, delayMs));
};

export const runRequestWithRetry = async <T>(
  action: () => Promise<T>,
): Promise<T> => {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await action();
    } catch (error) {
      const delayMs = REQUEST_RETRY_DELAYS_MS[attempt];
      if (delayMs === undefined || !isRetryableRequestError(error)) {
        throw error;
      }
      await sleep(delayMs);
    }
  }
};

declare global {
  // eslint-disable-next-line no-var
  var __e2eApiProxyStarted: boolean | undefined;
}

let proxyStartPromise: Promise<void> | null = null;
const ensureApiProxyIfNeeded = async () => {
  if (!process.env.E2E_PROXY_API) return;
  if (globalThis.__e2eApiProxyStarted) return;
  if (proxyStartPromise) return proxyStartPromise;

  proxyStartPromise = (async () => {
    const upstream = process.env.E2E_PROXY_UPSTREAM || "http://app-dev:8000";
    const upstreamUrl = new URL(upstream);

    const server = http.createServer((req, res) => {
      if (!req.url) {
        res.statusCode = 400;
        res.end("Missing url");
        return;
      }

      const target = new URL(req.url, upstreamUrl);
      const proxyReq = http.request(
        {
          protocol: upstreamUrl.protocol,
          hostname: upstreamUrl.hostname,
          port: upstreamUrl.port,
          method: req.method,
          path: target.pathname + target.search,
          headers: {
            ...req.headers,
            host: upstreamUrl.host,
          },
        },
        (proxyRes) => {
          res.writeHead(proxyRes.statusCode || 502, proxyRes.headers as any);
          proxyRes.pipe(res);
        },
      );

      proxyReq.on("error", () => {
        res.statusCode = 502;
        res.end("Bad gateway");
      });

      req.pipe(proxyReq);
    });

    await new Promise<void>((resolve) => {
      server.once("error", (err: any) => {
        if (err && err.code === "EADDRINUSE") {
          globalThis.__e2eApiProxyStarted = true;
          resolve();
          return;
        }
        throw err;
      });
      // Bind without an explicit host so `localhost` resolves for both IPv4/IPv6.
      server.listen(8071, () => {
        globalThis.__e2eApiProxyStarted = true;
        resolve();
      });
    });
  })();

  return proxyStartPromise;
};

export const keyCloakSignIn = async (
  page: Page,
  username: string,
  password: string,
  fromHome: boolean = true
) => {
  const explorerUrl = /\/explorer(?:\/|\?|$)/;
  const keycloakUrl = /\/realms\/[^/]+\/protocol\/openid-connect\/auth(?:\/|\?|$)/;

  // If the session is already authenticated, we may already be on the explorer.
  // Avoid going through Keycloak again in that case (can happen depending on storage state).
  try {
    await page.waitForURL(explorerUrl, { timeout: 2_000 });
    return;
  } catch {
    // Continue with the normal login flow.
  }

  if (fromHome) {
    const homeUrl = page.url();
    const signInButton = page.getByRole("button", { name: "Sign in" }).first();

    await expect(signInButton).toBeVisible({ timeout: 20_000 });
    await signInButton.click();

    try {
      await page.waitForURL(
        (url) => {
          const current = url.toString();
          return (
            current !== homeUrl ||
            explorerUrl.test(current) ||
            current.includes("/authenticate/") ||
            keycloakUrl.test(current)
          );
        },
        { waitUntil: "commit", timeout: 20_000 },
      );
    } catch (error) {
      // WebKit can occasionally stay on the home page after the first click even
      // though the button remains available. Retry the same user action once
      // before treating the auth transition as failed.
      if (page.url() === homeUrl && (await signInButton.isVisible().catch(() => false))) {
        await signInButton.click();
        await page.waitForURL(
          (url) => {
            const current = url.toString();
            return (
              current !== homeUrl ||
              explorerUrl.test(current) ||
              current.includes("/authenticate/") ||
              keycloakUrl.test(current)
            );
          },
          { waitUntil: "commit", timeout: 20_000 },
        );
      } else {
        throw error;
      }
    }
  }

  // Keycloak themes/i18n can vary; rely on stable form controls instead of localized headings.
  const usernameInput = page.locator('input[name="username"], input#username');
  const passwordInput = page.locator('input[name="password"], input#password');

  try {
    await expect(usernameInput).toBeVisible({ timeout: 20_000 });
  } catch (err) {
    // If we failed to reach Keycloak but are already logged in (redirect already happened),
    // treat it as a success.
    try {
      await page.waitForURL(explorerUrl, { timeout: 5_000 });
      return;
    } catch {
      // Fall through.
    }
    throw err;
  }

  await expect(passwordInput).toBeVisible({ timeout: 20_000 });

  if (await page.getByLabel("Restart login").isVisible()) {
    await page.getByLabel("Restart login").click();
  }

  await usernameInput.fill(username);
  await passwordInput.fill(password);
  await page.getByRole("button", { name: "Sign in" }).first().click();

  // Ensure the redirect back to Drive is committed before continuing.
  await page.waitForURL(explorerUrl, { waitUntil: "commit", timeout: 60_000 });
};

/**
 * Legacy-only helper kept for readiness control and transitional coverage.
 * Normal product specs must use deterministic bootstrap/cleanup fixtures instead.
 */
export const legacyClearDb = async (page?: Page) => {
  if (page) {
    try {
      await page.goto("about:blank", { waitUntil: "domcontentloaded" });
    } catch {
      // Ignore transient navigation failures while tearing down the previous page.
    }
    await page.context().clearCookies();
  }

  await ensureApiProxyIfNeeded();
  const origin = getE2EApiOrigin();
  try {
    const res = await postJson(`${origin}${LEGACY_E2E_CLEAR_DB_PATH}`, {});
    if (res.ok) return;
  } catch {
    // Fall back to Makefile target.
  }

  await runTarget(CLEAR_DB_TARGET);
};

/**
 * @deprecated Use `legacyClearDb()` only from readiness/transitional coverage.
 * New specs must not call this helper.
 */
export const clearDb = legacyClearDb;

export const bootstrapSession = async <T>(body: unknown): Promise<T> => {
  await ensureApiProxyIfNeeded();
  const res = await postJson(
    `${getE2EApiOrigin()}${E2E_BOOTSTRAP_SESSION_PATH}`,
    body,
  );
  return parseJsonResponse<T>(res, "E2E bootstrap-session");
};

export const bootstrapScenario = async <T>(body: unknown): Promise<T> => {
  await ensureApiProxyIfNeeded();
  const res = await postJson(
    `${getE2EApiOrigin()}${E2E_BOOTSTRAP_SCENARIO_PATH}`,
    body,
  );
  return parseJsonResponse<T>(res, "E2E bootstrap-scenario");
};

export const cleanupScope = async <T>(body: unknown): Promise<T> => {
  await ensureApiProxyIfNeeded();
  const res = await postJson(
    `${getE2EApiOrigin()}${E2E_CLEANUP_SCOPE_PATH}`,
    body,
  );
  return parseJsonResponse<T>(res, "E2E cleanup-scope");
};

export const ensureBootstrappedActorSession = async (
  page: Page,
  actor: WorkerActorFixture,
) => {
  await ensureApiProxyIfNeeded();
  const origin = getE2EApiOrigin();

  const meBefore = await runRequestWithRetry(() =>
    page.context().request.get(`${origin}/api/v1.0/users/me/`),
  );
  if (meBefore.ok()) return;

  const res = await runRequestWithRetry(() =>
    page.context().request.post(`${origin}${E2E_BOOTSTRAP_SESSION_PATH}`, {
      data: {
        run_id: actor.runId,
        worker_id: actor.workerId,
        actor_key: actor.actorKey,
        email: actor.actor.email,
        language: actor.actor.language ?? undefined,
        full_name: actor.actor.full_name ?? undefined,
        short_name: actor.actor.short_name ?? undefined,
      },
      headers: {
        "Content-Type": "application/json",
        ...getS2SHeaders(),
      },
    }),
  );
  await parseJsonResponse(res, "E2E browser-context bootstrap-session");

  const meAfter = await runRequestWithRetry(() =>
    page.context().request.get(`${origin}/api/v1.0/users/me/`),
  );
  if (!meAfter.ok()) {
    throw new Error(
      `E2E browser-context bootstrap-session did not yield /users/me: ${meAfter.status()}`,
    );
  }
};

export const runFixture = async (fixture: string) => {
  const origin = getE2EApiOrigin();
  try {
    const res = await postJson(`${origin}/api/v1.0/e2e/run-fixture/`, { fixture });
    if (res.ok) return;
  } catch {
    // Fall back to Makefile target.
  }

  await runTarget(`backend-exec-command ${fixture}`);
};

export const runTarget = async (target: string) => {
  await new Promise((resolve, reject) => {
    exec(
      `cd ${ROOT_PATH} && make ${target}`,
      (error: Error | null, stdout: string, stderr: string) => {
        if (error) {
          const combined = `${error.message}\n${stderr || ""}`;
          // Ignore "No rule to make target" errors
          if (combined.includes("make: *** No rule to make target")) {
            resolve(stdout);
            return;
          }
          // Some containers used for frontend-only E2E runs don't ship `make`.
          if (combined.includes("make: not found") || combined.includes("make: command not found")) {
            resolve(stdout);
            return;
          }
          console.error(`Error executing command: ${error}`);
          reject(error);
          return;
        }
        resolve(stdout);
      }
    );
  });
};

/**
 * Legacy-only helper kept for readiness control and transitional coverage.
 * Normal product specs must bootstrap authenticated actors via fixtures/auth.ts
 * or fixtures/actors.ts instead of calling user-auth directly.
 */
export const legacyLogin = async (page: Page, email: string) => {
  await ensureApiProxyIfNeeded();
  const origin = getE2EApiOrigin();
  const maxAttempts = 6;
  const authenticateInBrowserContext = async () => {
    const authResponse = await page.context().request.post(
      `${origin}${LEGACY_E2E_USER_AUTH_PATH}`,
      {
        data: { email },
        headers: { "Content-Type": "application/json" },
      },
    );

    if (!authResponse.ok()) {
      return {
        authOk: false,
        meOk: false,
      };
    }

    const meResponse = await page.context().request.get(
      `${origin}/api/v1.0/users/me/`,
    );

    return {
      authOk: true,
      meOk: meResponse.ok(),
    };
  };

  let lastAuthOk = false;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const result = await authenticateInBrowserContext();
    lastAuthOk = result.authOk;

    const cookies = await page.context().cookies();
    const hasSessionCookie = cookies.some(
      (cookie) => cookie.name === "drive_sessionid",
    );

    if (result.authOk && result.meOk && hasSessionCookie) {
      return;
    }

    if (attempt < maxAttempts - 1) {
      await page.waitForTimeout(500 * (attempt + 1));
    }
  }

  if (!lastAuthOk) {
    throw new Error("E2E user-auth failed");
  }

  throw new Error("E2E user-auth did not produce a usable browser session");
};

/**
 * @deprecated Use `legacyLogin()` only from readiness/transitional coverage.
 * New specs must not call this helper.
 */
export const login = legacyLogin;

export const getStorageState = (username: string) => {
  return `${__dirname}/../../playwright/.auth/user-${username}.json`;
};

export const dismissReleaseNotesIfPresent = async (
  page: Page,
  timeoutMs: number = 0
) => {
  const releaseNotes = page
    .getByRole("dialog")
    .filter({ hasText: /updates to drive/i });

  const close = releaseNotes.getByRole("button", { name: /^close$/i });
  if (await close.isVisible().catch(() => false)) {
    await close.click();
    await expect(releaseNotes).toBeHidden();
    return;
  }

  if (timeoutMs <= 0) return;
  try {
    await close.waitFor({ state: "visible", timeout: timeoutMs });
    await close.click();
    await expect(releaseNotes).toBeHidden();
  } catch {
    // Not shown for this user/session.
  }
};
