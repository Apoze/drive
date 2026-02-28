import { Page, expect } from "@playwright/test";
import {
  expectDefaultRoute,
  expectExplorerBreadcrumbs,
} from "./utils-explorer";
import { getRowItem } from "./utils-embedded-grid";
import { clickOnItemInTree } from "./utils-tree";
import { dismissReleaseNotesIfPresent } from "./utils-common";

export const clickToRecent = async (page: Page) => {
  await dismissReleaseNotesIfPresent(page);
  await page.getByRole("link", { name: "Recents" }).click({ noWaitAfter: true });
  await dismissReleaseNotesIfPresent(page);
  await expectDefaultRoute(page, "Recents", "/explorer/items/recent");
};

export const clickToMyFiles = async (page: Page) => {
  await dismissReleaseNotesIfPresent(page);
  const myFilesUrl = /\/explorer\/items\/my-files/;
  if (!myFilesUrl.test(page.url())) {
    const myFilesLink = page.getByRole("link", { name: "My files" });

    try {
      await myFilesLink.click({ noWaitAfter: true, timeout: 1_000 });
    } catch {
      try {
        await page.goto("/explorer/items/my-files", { waitUntil: "commit" });
      } catch {
        // SPA navigations can abort the initial `goto` request; rely on URL assertion below.
      }
    }

    try {
      await page.waitForURL(myFilesUrl, {
        timeout: 20_000,
        waitUntil: "commit",
      });
    } catch {
      // Navigation can be interrupted (ERR_ABORTED/frame detach) during SPA transitions.
      // Fall back to polling the current URL instead of failing hard.
      await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(myFilesUrl);
    }
  }
  await dismissReleaseNotesIfPresent(page);
  await expectDefaultRoute(page, "My files", "/explorer/items/my-files");
};

export const openMainWorkspaceFromMyFiles = async (page: Page) => {
  await clickToMyFiles(page);
  const mainWorkspace = await getRowItem(page, "My files");
  await mainWorkspace.dblclick();
  await page.waitForURL(/\/explorer\/items\/[0-9a-f-]{36}/, {
    timeout: 20_000,
  });
  await expectExplorerBreadcrumbs(page, ["My files"]);
};

export const clickToSharedWithMe = async (page: Page) => {
  await dismissReleaseNotesIfPresent(page);
  // After `page.goto("/")`, the app can still be redirecting to the last/default explorer route
  // (often `/explorer/items/my-files`). Wait for this initial navigation to settle before
  // triggering a new left-bar navigation, otherwise WebKit can interrupt our click/goto.
  try {
    await page.waitForURL(/\/explorer\//, { timeout: 20_000, waitUntil: "commit" });
  } catch {
    // If we're already on an explorer route (or the redirect happens via SPA), proceed.
  }

  const sharedWithMeUrl = /\/explorer\/items\/shared-with-me/;
  const sharedWithMeLink = page.getByRole("link", { name: "Shared with me" });
  try {
    await sharedWithMeLink.click({ noWaitAfter: true, timeout: 20_000 });
  } catch {
    try {
      await page.goto("/explorer/items/shared-with-me", {
        // The first visit can trigger Next.js dev compilation; wait for DOM content.
        waitUntil: "domcontentloaded",
      });
    } catch {
      // SPA navigations can abort the initial `goto` request; rely on URL assertion below.
    }
  }

  // The click can occasionally be ignored while the explorer is still settling (Firefox flake).
  // Ensure we land on the expected route, with a deterministic fallback to `goto`.
  try {
    await page.waitForURL(sharedWithMeUrl, { timeout: 20_000, waitUntil: "commit" });
  } catch {
    try {
      await page.goto("/explorer/items/shared-with-me", { waitUntil: "domcontentloaded" });
      await page.waitForURL(sharedWithMeUrl, { timeout: 20_000, waitUntil: "commit" });
    } catch {
      await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(sharedWithMeUrl);
    }
  }
  await dismissReleaseNotesIfPresent(page);
  await expectDefaultRoute(page, "Shared with me", "/explorer/items/shared-with-me");
};

export const clickToTrash = async (page: Page) => {
  await dismissReleaseNotesIfPresent(page);
  await expect(page.getByTestId("default-route-button")).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("link", { name: "Trash" }).click({ noWaitAfter: true });

  const trashUrl = /\/explorer\/trash/;
  try {
    await page.waitForURL(trashUrl, { timeout: 20_000, waitUntil: "commit" });
  } catch {
    await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(trashUrl);
  }

  const breadcrumbs = page.getByTestId("trash-page-breadcrumbs");
  await expect(breadcrumbs).toBeVisible({ timeout: 20_000 });
  await expect(breadcrumbs).toContainText("Trash");
  const currentUrl = page.url();
  expect(currentUrl).toContain("/explorer/trash");
};

export const clickToFavorites = async (page: Page) => {
  await dismissReleaseNotesIfPresent(page);
  await clickOnItemInTree(page, "Starred");
  await expectDefaultRoute(page, "Starred", "/explorer/items/favorites");
};

export const navigateToFolder = async (
  page: Page,
  folderName: string,
  expectedBreadcrumbs: string[]
) => {
  const folderItem = await getRowItem(page, folderName);
  await folderItem.dblclick();
  await page.waitForLoadState("commit");
  await dismissReleaseNotesIfPresent(page);
  await expectExplorerBreadcrumbs(page, expectedBreadcrumbs);
};
