import { expect, type Page } from "@playwright/test";

import { test } from "./fixtures/actors";

const mockConfig = async (
  page: Page,
  mutate: (json: Record<string, unknown>) => void,
) => {
  await page.route("**/api/v1.0/config/", async (route) => {
    const response = await route.fetch();
    const json = (await response.json()) as Record<string, unknown>;
    mutate(json);
    await route.fulfill({ response, json });
  });
};

test.describe("Custom CSS and JS injection", () => {
  test("should inject a stylesheet link when FRONTEND_CSS_URL is set", async ({
    page,
  }) => {
    const cssUrl = "https://example.com/custom.css";
    await mockConfig(page, (json) => {
      json.FRONTEND_CSS_URL = cssUrl;
    });

    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "Open user menu" }),
    ).toBeVisible({ timeout: 20_000 });

    const linkEl = page.locator(`link[rel="stylesheet"][href="${cssUrl}"]`);
    await expect(linkEl).toBeAttached();
  });

  test("should NOT inject a stylesheet link when FRONTEND_CSS_URL is not set", async ({
    page,
  }) => {
    await mockConfig(page, (json) => {
      delete json.FRONTEND_CSS_URL;
    });

    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "Open user menu" }),
    ).toBeVisible({ timeout: 20_000 });

    const linkEl = page.locator(
      'link[rel="stylesheet"][href="https://example.com/custom.css"]',
    );
    await expect(linkEl).not.toBeAttached();
  });

  test("should inject a script tag when FRONTEND_JS_URL is set", async ({
    page,
  }) => {
    const jsUrl = "https://example.com/custom.js";
    await mockConfig(page, (json) => {
      json.FRONTEND_JS_URL = jsUrl;
    });

    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "Open user menu" }),
    ).toBeVisible({ timeout: 20_000 });

    const scriptEl = page.locator(`script[src="${jsUrl}"]`);
    await expect(scriptEl).toBeAttached();
  });

  test("should NOT inject a script tag when FRONTEND_JS_URL is not set", async ({
    page,
  }) => {
    await mockConfig(page, (json) => {
      delete json.FRONTEND_JS_URL;
    });

    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "Open user menu" }),
    ).toBeVisible({ timeout: 20_000 });

    const scriptEl = page.locator(
      'script[src="https://example.com/custom.js"]',
    );
    await expect(scriptEl).not.toBeAttached();
  });
});
