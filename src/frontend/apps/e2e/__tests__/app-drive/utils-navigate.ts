import { Page, expect } from "@playwright/test";
import {
  expectDefaultRoute,
  expectExplorerBreadcrumbs,
} from "./utils-explorer";
import { getRowItem, waitForExplorerGridToSettle } from "./utils-embedded-grid";
import { clickOnItemInTree } from "./utils-tree";
import { dismissReleaseNotesIfPresent } from "./utils-common";

export const clickToRecent = async (page: Page) => {
  await dismissReleaseNotesIfPresent(page);
  const recentUrl = /\/explorer\/items\/recent/;
  const recentTarget = page
    .getByRole("link", { name: "Recents" })
    .or(page.getByRole("button", { name: "Recents" }))
    .first();

  try {
    await recentTarget.click({ noWaitAfter: true, timeout: 10_000 });
  } catch {
    try {
      await page.goto("/explorer/items/recent", { waitUntil: "domcontentloaded" });
    } catch {
      // SPA navigations can abort the initial `goto` request; rely on URL assertion below.
    }
  }

  try {
    await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(recentUrl);
  } catch {
    await page.goto("/explorer/items/recent", { waitUntil: "domcontentloaded" });
    await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(recentUrl);
  }

  await dismissReleaseNotesIfPresent(page);
  await expectDefaultRoute(page, "Recents", "/explorer/items/recent");
  await waitForExplorerGridToSettle(page);
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
  await waitForExplorerGridToSettle(page);
};

export const openMainWorkspaceFromMyFiles = async (page: Page) => {
  await clickToMyFiles(page);
  const mainWorkspace = await getRowItem(page, "My files");
  await mainWorkspace.dblclick();
  const workspaceUrl = /\/explorer\/items\/[0-9a-f-]{36}/;
  try {
    await page.waitForURL(workspaceUrl, {
      timeout: 20_000,
      waitUntil: "commit",
    });
  } catch {
    await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(workspaceUrl);
  }
  // With root breadcrumbs enabled, the default route ("My files") is shown as the
  // first breadcrumb item, and the main workspace (also named "My files") is the
  // second item after navigation.
  await expectExplorerBreadcrumbs(page, ["My files", "My files"]);
  await waitForExplorerGridToSettle(page);
};

export const openWorkspaceFromMyFiles = async (
  page: Page,
  folderName: string,
  folderId?: string,
) => {
  await openMainWorkspaceFromMyFiles(page);
  try {
    await navigateToFolder(page, folderName, getMainWorkspaceBreadcrumbs(folderName));
  } catch (error) {
    if (!folderId) {
      throw error;
    }

    const folderUrlPath = `/explorer/items/${folderId}`;
    const folderUrl = new RegExp(`${folderUrlPath}(?:$|[/?#])`);

    try {
      await page.goto(folderUrlPath, {
        timeout: 5_000,
        waitUntil: "commit",
      });
    } catch {
      // SPA navigations can abort or stall the initial `goto`; rely on URL checks below.
    }

    try {
      await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(folderUrl);
    } catch {
      try {
        await page.goto(folderUrlPath, {
          timeout: 1_000,
          waitUntil: "commit",
        });
      } catch {
        // Keep the retry helper-local and let the final URL assertion decide success.
      }

      await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(folderUrl);
    }

    await dismissReleaseNotesIfPresent(page);
    await waitForExplorerGridToSettle(page);
    await expectExplorerBreadcrumbs(page, getMainWorkspaceBreadcrumbs(folderName));
  }
};

export const getMainWorkspaceBreadcrumbs = (...segments: string[]) => {
  return ["My files", "My files", ...segments];
};

export const openFolderFromMainWorkspace = async (
  page: Page,
  folderName: string,
  folderId?: string,
) => {
  await openWorkspaceFromMyFiles(page, folderName, folderId);
};

export const clickToSharedWithMe = async (page: Page) => {
  await dismissReleaseNotesIfPresent(page);
  const sharedWithMeUrl = /\/explorer\/items\/shared-with-me/;
  // The left-bar can expose routes as either links or buttons depending on the UI kit/rendering.
  // Prefer an actionability-friendly locator and keep the navigation deterministic.
  const sharedWithMeTarget = page
    .getByRole("link", { name: "Shared with me" })
    .or(page.getByRole("button", { name: "Shared with me" }))
    .first();
  try {
    await sharedWithMeTarget.click({ noWaitAfter: true, timeout: 10_000 });
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

  // Firefox can miss the "commit" navigation signal on SPA transitions; prefer URL polling.
  // Ensure we land on the expected route, with a deterministic fallback to `goto`.
  try {
    await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(sharedWithMeUrl);
  } catch {
    await page.goto("/explorer/items/shared-with-me", { waitUntil: "domcontentloaded" });
    await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(sharedWithMeUrl);
  }
  await dismissReleaseNotesIfPresent(page);
  await expectDefaultRoute(page, "Shared with me", "/explorer/items/shared-with-me");
  await waitForExplorerGridToSettle(page);
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
  const favoritesUrl = /\/explorer\/items\/favorites/;

  try {
    await clickOnItemInTree(page, "Starred");
  } catch {
    // Fall back to direct navigation below.
  }

  // Match the deterministic fallback shape used by other default-route helpers:
  // if the initial UI navigation does not converge to the favorites URL, force
  // a direct route navigation and assert the final URL there.
  try {
    await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(favoritesUrl);
  } catch {
    await page.goto("/explorer/items/favorites", { waitUntil: "domcontentloaded" });
    await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(favoritesUrl);
  }

  await dismissReleaseNotesIfPresent(page);
  await expectDefaultRoute(page, "Starred", "/explorer/items/favorites");
  await waitForExplorerGridToSettle(page);
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
  await waitForExplorerGridToSettle(page);
};
