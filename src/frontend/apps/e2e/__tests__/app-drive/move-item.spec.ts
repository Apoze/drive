import test, { expect } from "@playwright/test";
import { clearDb, login } from "./utils-common";
import { clickToMyFiles, navigateToFolder, openMainWorkspaceFromMyFiles } from "./utils-navigate";
import { clickOnRowItemActions, expectRowItem, getRowItem } from "./utils-embedded-grid";
import {
  acceptMoveItem,
  clickAndAcceptMoveToRoot,
  getMoveFolderModal,
  searchAndSelectItem,
} from "./utils/move-utils";
import { createFolderInCurrentFolder } from "./utils-item";
import { expectExplorerBreadcrumbs } from "./utils-explorer";

test("Move an item to a new folder", async ({ page }) => {
  await clearDb();
  await login(page, "drive@example.com");
  await page.goto("/");
  await openMainWorkspaceFromMyFiles(page);
  await createFolderInCurrentFolder(page, "John");
  await createFolderInCurrentFolder(page, "Doe");
  const JohnRow = await getRowItem(page, "John");
  await expect(JohnRow).toBeVisible();
  await clickOnRowItemActions(page, "John", "Move");
  const moveFolderModal = await getMoveFolderModal(page);
  const DoeRow = moveFolderModal
    .getByRole("row", { name: /^Doe\b/i })
    .first();
  await expect(DoeRow).toBeVisible({ timeout: 20_000 });
  await DoeRow.click();
  await acceptMoveItem(page);
  await expect(JohnRow).not.toBeVisible();
});

test("Search and select to move an item", async ({ page }) => {
  await clearDb();
  await login(page, "drive@example.com");
  await page.goto("/");
  await openMainWorkspaceFromMyFiles(page);
  // Create the folder structure
  await createFolderInCurrentFolder(page, "John");
  await createFolderInCurrentFolder(page, "Doe");
  await navigateToFolder(page, "Doe", ["My files", "Doe"]);
  await createFolderInCurrentFolder(page, "Jane");
  await navigateToFolder(page, "Jane", ["My files", "Doe", "Jane"]);
  await createFolderInCurrentFolder(page, "Jim");

  // return to my files
  await openMainWorkspaceFromMyFiles(page);

  // Search and select to move an item
  const JohnRow = await getRowItem(page, "John");

  await expect(JohnRow).toBeVisible();
  await clickOnRowItemActions(page, "John", "Move");
  await searchAndSelectItem(page, "Jim");
  const moveFolderModal = await getMoveFolderModal(page);
  await expectExplorerBreadcrumbs(moveFolderModal, [
    "My files",
    "Doe",
    "Jane",
    "Jim",
  ]);
  await acceptMoveItem(page);

  await openMainWorkspaceFromMyFiles(page);
  await expect(JohnRow).not.toBeVisible();
  await navigateToFolder(page, "Doe", ["My files", "Doe"]);
  await navigateToFolder(page, "Jane", ["My files", "Doe", "Jane"]);
  await navigateToFolder(page, "Jim", ["My files", "Doe", "Jane", "Jim"]);
  await expect(JohnRow).toBeVisible();
});

test("Move item to root", async ({ page }) => {
  await clearDb();
  await login(page, "drive@example.com");
  await page.goto("/");
  await openMainWorkspaceFromMyFiles(page);
  // Create the folder structure
  await createFolderInCurrentFolder(page, "John");
  await navigateToFolder(page, "John", ["My files", "John"]);
  await createFolderInCurrentFolder(page, "Doe");
  await clickToMyFiles(page);
  await expectRowItem(page, "My files");
  await expect(page.getByRole("button", { name: "Doe", exact: true })).not.toBeVisible();
  await openMainWorkspaceFromMyFiles(page);
  await navigateToFolder(page, "John", ["My files", "John"]);
  const DoeRow = await getRowItem(page, "Doe");
  await expect(DoeRow).toBeVisible();
  await clickOnRowItemActions(page, "Doe", "Move");
  await clickAndAcceptMoveToRoot(page);
  await expect(DoeRow).not.toBeVisible();
  await clickToMyFiles(page);
  await expectRowItem(page, "Doe");
});
