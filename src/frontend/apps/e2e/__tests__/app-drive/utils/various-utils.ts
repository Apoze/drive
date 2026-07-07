import { Browser, BrowserContext, Page } from "@playwright/test";

export const createAnonymousBrowserContext = async (browser: Browser) =>
  browser.newContext({ storageState: { cookies: [], origins: [] } });

export const forceAnonymousFrontendConfig = async (
  page: Page,
  overrides: Record<string, unknown> = {},
) => {
  await page.route("**/api/v1.0/config/", async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    await route.fulfill({
      response,
      json: {
        ...json,
        FRONTEND_SILENT_LOGIN_ENABLED: false,
        ...overrides,
      },
    });
  });
};

export const installClipboardShim = async (context: BrowserContext) => {
  await context.addInitScript(() => {
    // Some E2E origins are plain HTTP (LAN dev), where `navigator.clipboard` may be undefined.
    // Provide a minimal shim so the "Copy link" UI works without crashing.
    (window as any).__e2eClipboardText = "";
    const clipboard = {
      writeText: async (text: string) => {
        (window as any).__e2eClipboardText = String(text || "");
      },
      readText: async () => String((window as any).__e2eClipboardText || ""),
    };
    try {
      Object.defineProperty(navigator, "clipboard", {
        value: clipboard,
        configurable: true,
      });
    } catch {
      // ignore
    }
  });
};

export const grantClipboardPermissions = async (
  browserName: string,
  context: BrowserContext,
) => {
  if (browserName === "chromium" || browserName === "webkit") {
    await context.grantPermissions(["clipboard-read"]);
  }
};
