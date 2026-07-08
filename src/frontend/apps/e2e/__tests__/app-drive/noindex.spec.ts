import { expect } from "@playwright/test";

import { test } from "./fixtures/auth";

test.describe("Search engine indexing prevention", () => {
  test("serves app pages with a robots noindex meta tag", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "User menu" }),
    ).toBeVisible({ timeout: 20_000 });

    await expect(
      page.locator('meta[name="robots"][content="noindex"]'),
    ).toBeAttached();
  });

  test("serves robots.txt that allows crawling", async ({ page }) => {
    const response = await page.request.get("/robots.txt");
    expect(response.status()).toBe(200);

    const content = await response.text();
    expect(content).toContain("User-agent: *");

    const rules = content
      .split("\n")
      .filter((line) => !line.startsWith("#"))
      .join("\n");
    expect(rules).not.toMatch(/Disallow: \//);
  });

  test("serves pages with a X-Robots-Tag noindex header", async ({
    page,
  }) => {
    test.skip(
      !process.env.CI,
      "the header is added by nginx, not by the local dev server",
    );

    const response = await page.request.get("/");
    expect(response.headers()["x-robots-tag"]).toBe("noindex");
  });
});
