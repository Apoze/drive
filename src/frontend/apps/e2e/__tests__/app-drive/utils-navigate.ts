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
  if (!page.url().includes("/explorer/items/my-files")) {
    try {
      await page.goto("/explorer/items/my-files", { waitUntil: "commit" });
    } catch {
      // SPA navigations can abort the initial `goto` request; rely on URL assertion below.
    }
    await page.waitForURL(/\/explorer\/items\/my-files/, { timeout: 20_000 });
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
  await page
    .getByRole("link", { name: "Shared with me" })
    .click({ noWaitAfter: true });
  await dismissReleaseNotesIfPresent(page);
  await expectDefaultRoute(
    page,
    "Shared with me",
    "/explorer/items/shared-with-me"
  );
};

export const clickToTrash = async (page: Page) => {
  await dismissReleaseNotesIfPresent(page);
  await page.getByRole("link", { name: "Trash" }).click({ noWaitAfter: true });
  const breadcrumbs = page.getByTestId("trash-page-breadcrumbs");
  await expect(breadcrumbs).toBeVisible();
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
  await expectExplorerBreadcrumbs(page, expectedBreadcrumbs);
};
