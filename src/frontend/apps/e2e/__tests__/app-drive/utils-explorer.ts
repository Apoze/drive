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
    // The breadcrumbs container also includes non-breadcrumb buttons (e.g. menu triggers).
    // Scope assertions to the breadcrumb items themselves.
    const breadcrumbButtons = breadcrumbs.locator(
      // Some crumbs use stable test ids, others use Cunningham breadcrumb buttons,
      // and the last crumb can be a plain <button> inside the embedded-explorer wrapper.
      '[data-testid="default-route-button"],[data-testid="breadcrumb-button"],.c__breadcrumbs__button,.embedded-explorer__breadcrumbs__last-item button',
    );
    const normalize = (value: string) =>
      value
        .replace(/arrow_drop_(down|up)/g, "")
        .trim()
        .replace(/\s+/g, " ");

    const normalizeList = (values: string[]) =>
      values
        .map(normalize)
        .filter(Boolean)
        .map((v) => v.toLowerCase());

    await expect
      .poll(
        async () => {
          const texts = await breadcrumbButtons.allTextContents();
          const actual = normalizeList(Array.isArray(texts) ? texts : []);
          const exp = normalizeList(expected);

          // Some flows (e.g. move modal) include a global "All folders" root breadcrumb.
          // Tests typically assert relative to the workspace; tolerate this extra root.
          if (actual[0] === "all folders" && exp[0] !== "all folders") {
            actual.shift();
          }

          // In this fork, the main workspace is also named "My files".
          // With root breadcrumbs enabled, "My files" can appear twice at the start
          // (default-route + workspace). Normalize that duplicate for deterministic tests.
          if (
            exp.length >= 1 &&
            actual.length === exp.length + 1 &&
            actual[0] === exp[0] &&
            actual[1] === exp[0]
          ) {
            actual.splice(1, 1);
          }

          return actual;
        },
        { timeout: 30_000 },
      )
      .toEqual(normalizeList(expected));
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
  // Ensure the SPA navigation is committed before asserting UI state.
  await expect
    .poll(() => page.url(), { timeout: 20_000 })
    .toContain(route);
  const defaultRouteButton = page.getByTestId("default-route-button");
  await expect(defaultRouteButton).toBeVisible({ timeout: 20_000 });
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
