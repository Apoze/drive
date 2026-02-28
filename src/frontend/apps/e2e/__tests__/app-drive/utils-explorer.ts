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
    const breadcrumbButtons = breadcrumbs.locator(".c__breadcrumbs__button");
    await expect(breadcrumbButtons).toHaveCount(expected.length);

    for (let i = 0; i < expected.length; i++) {
      const button = breadcrumbButtons.nth(i);
      await expect(button).toBeVisible();
      await expect(button).toContainText(expected[i]);
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
  await expect(defaultRouteButton).toBeVisible();
  await expect(defaultRouteButton).toContainText(breadcrumbLabel);
  await page.waitForURL((url) => url.toString().includes(route));
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
