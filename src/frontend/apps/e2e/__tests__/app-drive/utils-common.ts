import { expect, Page } from "@playwright/test";
import { exec } from "child_process";
import http from "http";
import path from "path";
import { URL } from "url";
// We need to use __dirname to get the root path of the project
// because Playwright runs tests in a different directory from the root
// by default.
const ROOT_PATH = path.join(__dirname, "/../../../../../..");
const CLEAR_DB_TARGET = "clear-db-e2e";
const DEFAULT_API_ORIGIN = "http://192.168.10.123:8071";

const getS2SHeaders = () => {
  const token = process.env.E2E_S2S_TOKEN;
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
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
  if (fromHome) {
    await page.getByRole("button", { name: "Sign in" }).first().click();
  }

  await expect(page.getByText("Sign in to your account").first()).toBeVisible();

  if (await page.getByLabel("Restart login").isVisible()) {
    await page.getByLabel("Restart login").click();
  }

  await page.getByRole("textbox", { name: "username" }).fill(username);
  await page.getByRole("textbox", { name: "password" }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).first().click();
};

export const clearDb = async () => {
  await ensureApiProxyIfNeeded();
  const origin = process.env.E2E_API_ORIGIN || DEFAULT_API_ORIGIN;
  if (process.env.E2E_S2S_TOKEN) {
    try {
      const res = await postJson(`${origin}/api/v1.0/e2e/clear-db/`, {});
      if (res.ok) return;
    } catch {
      // Fall back to Makefile target.
    }
  }

  await runTarget(CLEAR_DB_TARGET);
};

export const runFixture = async (fixture: string) => {
  const origin = process.env.E2E_API_ORIGIN || DEFAULT_API_ORIGIN;
  if (process.env.E2E_S2S_TOKEN) {
    try {
      const res = await postJson(`${origin}/api/v1.0/e2e/run-fixture/`, { fixture });
      if (res.ok) return;
    } catch {
      // Fall back to Makefile target.
    }
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

export const login = async (page: Page, email: string) => {
  await ensureApiProxyIfNeeded();
  const origin = process.env.E2E_API_ORIGIN || DEFAULT_API_ORIGIN;
  await page.request.post(`${origin}/api/v1.0/e2e/user-auth/`, {
    data: {
      email,
    },
  });
};

export const getStorageState = (username: string) => {
  return `${__dirname}/../../playwright/.auth/user-${username}.json`;
};
