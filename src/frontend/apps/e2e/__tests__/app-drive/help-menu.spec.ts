import { expect, type Page } from "@playwright/test";

import { test } from "./fixtures/actors";

const HELP_MENU_CONFIG = {
  documentationUrl: "https://example.com/docs",
  legal: {
    termsOfUseUrl: "https://example.com/tos",
  },
  supportEmail: "mailto:support@example.com",
};

const overrideHelpMenuConfig = async (
  page: Page,
  helpMenuConfig: unknown,
) => {
  await page.route("**/api/v1.0/config/", async (route) => {
    const response = await route.fetch();
    const json = (await response.json()) as Record<string, unknown>;
    if (helpMenuConfig === undefined) {
      delete json.FRONTEND_HELP_MENU_CONFIG;
    } else {
      json.FRONTEND_HELP_MENU_CONFIG = helpMenuConfig;
    }
    await route.fulfill({ response, json });
  });
};

test.describe("Help menu", () => {
  test("renders the help menu with configured options", async ({ page }) => {
    await overrideHelpMenuConfig(page, HELP_MENU_CONFIG);
    await page.goto("/");

    const footer = page.locator(".c__left-panel__footer__drive");
    await expect(footer).toBeVisible({ timeout: 20_000 });

    await footer.getByRole("button", { name: "Help" }).click();

    await expect(
      page.getByRole("menuitem", { name: "Documentation" }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: "Contact us" }),
    ).toBeVisible();
  });

  test("does not render the contact option without support email", async ({
    page,
  }) => {
    await overrideHelpMenuConfig(page, {
      documentationUrl: HELP_MENU_CONFIG.documentationUrl,
    });
    await page.goto("/");

    const footer = page.locator(".c__left-panel__footer__drive");
    await footer.getByRole("button", { name: "Help" }).click();

    await expect(
      page.getByRole("menuitem", { name: "Documentation" }),
    ).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Contact us" })).toHaveCount(
      0,
    );
  });

  test("does not render the help menu with an empty config", async ({
    page,
  }) => {
    await overrideHelpMenuConfig(page, {});
    await page.goto("/");

    await expect(
      page.getByRole("button", { name: "Open user menu" }),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.locator(".c__left-panel__footer__drive")).toHaveCount(0);
  });
});
