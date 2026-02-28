import { expect, Page } from "@playwright/test";
import { expectTreeItemIsSelected } from "./utils-tree";
import { PageOrLocator } from "./utils/types-utils";

export const expectExplorerBreadcrumbs = async (
  page: PageOrLocator,
  expected: string[],
  hidden: string[] = [],
) => {
  const breadcrumbs = page.getByTestId("explorer-breadcrumbs");
  await expect(breadcrumbs).toBeVisible();

  // Check the order of breadcrumbs
  if (expected.length >= 1) {
    const breadcrumbButtonsByTestId = breadcrumbs.locator(
      '[data-testid="default-route-button"], [data-testid="breadcrumb-button"]',
    );
    const hasTestIdButtons = (await breadcrumbButtonsByTestId.count()) > 0;
    const breadcrumbButtons = hasTestIdButtons
      ? breadcrumbButtonsByTestId
      : breadcrumbs.getByRole("button");
    await expect
      .poll(() => breadcrumbButtons.count(), { timeout: 5000 })
      .toBeGreaterThanOrEqual(expected.length);

    const actual = (await breadcrumbButtons.allTextContents()).map((t) =>
      t.trim().replace(/\s+/g, " "),
    );

    const asAny = page as any;
    const canOpenMenu =
      typeof asAny.keyboard !== "undefined" &&
      typeof asAny.locator === "function" &&
      typeof asAny.getByRole === "function";

    let breadcrumbMenuEntries: string[] = [];
    const getMenuEntries = async () => {
      if (!canOpenMenu) return [];
      const trigger = breadcrumbs.locator(".c__dropdown-menu-trigger").last();
      try {
        await trigger.waitFor({ state: "visible", timeout: 1000 });
      } catch {
        return [];
      }
      try {
        await trigger.click();
      } catch {
        return [];
      }

      const menu = asAny
        .locator(
          '.c__dropdown-menu[role="menu"], .c__dropdown-menu, [role="menu"]',
        )
        .first();
      try {
        await menu.waitFor({ state: "visible", timeout: 2000 });
      } catch {
        try {
          await asAny.keyboard.press("Escape");
        } catch {
          // ignore
        }
        return [];
      }

      const entries = (await menu
        .locator('[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]')
        .allTextContents())
        .map((t: string) => t.trim().replace(/\s+/g, " "))
        .filter(Boolean);

      try {
        await asAny.keyboard.press("Escape");
      } catch {
        // ignore
      }
      return entries;
    };

    let searchStart = 0;
    for (const label of expected) {
      const index = actual
        .slice(searchStart)
        .findIndex((t) => t.includes(label));
      if (index >= 0) {
        searchStart += index + 1;
        continue;
      }

      // Some intermediate crumbs can be hidden behind a dropdown when the breadcrumb bar
      // collapses (e.g. long paths). If we can't find a crumb in the visible buttons, try
      // to discover it in the breadcrumb dropdown menu.
      if (breadcrumbMenuEntries.length === 0) {
        breadcrumbMenuEntries = await getMenuEntries();
      }
      if (breadcrumbMenuEntries.some((t) => t.includes(label))) {
        continue;
      }

      expect(
        index,
        `Missing breadcrumb: "${label}" in: ${actual.join(" > ")} (menu: ${breadcrumbMenuEntries.join(" | ")})`,
      ).toBeGreaterThanOrEqual(0);
    }
  }
};

export const expectCurrentFolder = async (
  page: Page,
  expected: string[],
  isSelected: boolean = false,
) => {
  await expectTreeItemIsSelected(
    page,
    expected[expected.length - 1],
    isSelected,
  );
  await expectExplorerBreadcrumbs(page, expected);
};

export const expectDefaultRoute = async (
  page: Page,
  breadcrumbLabel: string,
  route: string,
) => {
  const defaultRouteButton = page.getByTestId("default-route-button");
  await expect(defaultRouteButton).toBeVisible({ timeout: 20_000 });

  try {
    await page.waitForURL((url) => url.toString().includes(route), {
      timeout: 20_000,
      waitUntil: "commit",
    });
  } catch {
    await expect
      .poll(() => page.url(), { timeout: 20_000 })
      .toContain(route);
  }

  await expect(defaultRouteButton).toContainText(breadcrumbLabel, {
    timeout: 20_000,
  });
};

export const clickOnBreadcrumbButtonAction = async (
  page: Page,
  actionName: string,
) => {
  if (actionName === "Share") {
    const rightPanel = page.getByTestId("right-panel");
    const shareButton = rightPanel.getByRole("button", { name: /^Share$/i });
    try {
      await shareButton.waitFor({ state: "visible", timeout: 2_000 });
      await shareButton.click();
      return;
    } catch {
      // Fallback to dropdown menu below.
    }
  }

  if (actionName === "Delete") {
    const selectionBar = page.locator(".explorer__selection-bar");
    try {
      await selectionBar.waitFor({ state: "visible", timeout: 5_000 });
      const deleteButton = selectionBar.getByRole("button", { name: /^Delete$/i });
      await expect(deleteButton).toBeVisible({ timeout: 20_000 });
      await deleteButton.click();

      // Some flows require confirming deletion in a modal.
      const confirmDialog = page
        .getByRole("dialog")
        .filter({ has: page.getByRole("button", { name: /^Delete$/i }) })
        .first();
      try {
        await confirmDialog.waitFor({ state: "visible", timeout: 2_000 });
        await confirmDialog.getByRole("button", { name: /^Delete$/i }).click();
      } catch {
        // No confirmation dialog detected; continue.
      }
      return;
    } catch {
      // Fallback to dropdown menu below.
    }
  }

  const breadcrumbs = page.getByTestId("explorer-breadcrumbs");
  await expect(breadcrumbs).toBeVisible();
  const trigger = breadcrumbs.locator(".c__dropdown-menu-trigger").last();
  try {
    await trigger.waitFor({ state: "visible", timeout: 5_000 });
    await trigger.click();
  } catch {
    const fallbackButton = breadcrumbs
      .getByTestId("breadcrumb-button")
      .filter({ hasText: "arrow_drop_down" })
      .last();
    await fallbackButton.click();
  }

  const menu = page
    .locator('.c__dropdown-menu[role="menu"], .c__dropdown-menu, [role="menu"]')
    .first();
  await menu.waitFor({ state: "visible", timeout: 10_000 });

  const candidates = [
    menu.locator(`[role="menuitem"][aria-label="${actionName}"]`),
    menu.getByRole("menuitem", { name: actionName }),
    menu.locator('[role="menuitem"]').filter({ hasText: actionName }),
    menu.locator(".c__dropdown-menu-item__label").filter({ hasText: actionName }),
    menu.getByText(actionName, { exact: true }),
  ];

  for (const candidate of candidates) {
    try {
      const first = candidate.first();
      await first.waitFor({ state: "visible", timeout: 5_000 });
      await first.click();
      return;
    } catch {
      // Try next locator shape.
    }
  }

  throw new Error(`Could not find action "${actionName}" in opened menu`);
};
