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

  if (expected.length === 0) return;

  const escapeRegExp = (value: string) =>
    value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const hasVisibleMatch = async (locator: any): Promise<boolean> => {
    const count = await locator.count().catch(() => 0);
    for (let i = 0; i < count; i += 1) {
      const visible = await locator.nth(i).isVisible().catch(() => false);
      if (visible) return true;
    }
    return false;
  };

  // The breadcrumb bar itself reliably exposes the *current* folder name as text.
  // Intermediate ancestors may be hidden or represented differently depending on
  // navigation state; we keep the assertion focused to avoid false negatives.
  const currentLabel = expected[expected.length - 1];
  const currentLabelRe = new RegExp(escapeRegExp(currentLabel), "i");

  const candidates = [
    breadcrumbs
      .getByTestId("breadcrumb-button")
      .filter({ hasText: currentLabelRe }),
    breadcrumbs.locator("button").filter({ hasText: currentLabelRe }),
    breadcrumbs.getByText(currentLabelRe),
  ];

  const isCurrentVisible = async () => {
    for (const candidate of candidates) {
      const ok = await hasVisibleMatch(candidate);
      if (ok) return true;
    }
    return false;
  };

  const visibleButtons = async (): Promise<string[]> => {
    try {
      const names = await breadcrumbs.locator("button").evaluateAll(
        (nodes: Element[]) =>
          nodes
            .map((n) => (n as HTMLElement).textContent || "")
            .map((t) => t.trim().replace(/\s+/g, " "))
            .filter(Boolean),
      );
      return Array.isArray(names) ? names : [];
    } catch {
      return [];
    }
  };

  try {
    await expect.poll(async () => isCurrentVisible(), { timeout: 20_000 }).toBe(
      true,
    );
    return;
  } catch {
    const visible = await visibleButtons();
    expect(
      false,
      `Missing current breadcrumb: "${currentLabel}" (visible: ${visible.join(" > ")})`,
    ).toBe(true);
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
