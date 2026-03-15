import { expect } from "@playwright/test";
import { test } from "./fixtures/scenarios";
import {
  clickToMyFiles,
  getMainWorkspaceBreadcrumbs,
  navigateToFolder,
  openFolderFromMainWorkspace,
} from "./utils-navigate";
import {
  clickOnRowItemActions,
  expectRowItem,
  expectRowItemIsNotVisible,
  getRowItem,
} from "./utils-embedded-grid";
import {
  acceptMoveItem,
  clickAndAcceptMoveToRoot,
  getMoveFolderModal,
  searchAndSelectItem,
} from "./utils/move-utils";
import { createFolderInCurrentFolder } from "./utils-item";
import { expectDefaultRoute, expectExplorerBreadcrumbs } from "./utils-explorer";

test("Move an item to a new folder", async ({ page, isolatedWorkspace }) => {
  const rootTitle = isolatedWorkspace.result.workspace_root.title;
  await page.goto("/");
  await openFolderFromMainWorkspace(page, rootTitle);
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
  await expectRowItemIsNotVisible(page, "John");
});

test("Search and select to move an item", async ({
  page,
  isolatedWorkspace,
}, testInfo) => {
  testInfo.setTimeout(120000);
  const rootTitle = isolatedWorkspace.result.workspace_root.title;
  await page.goto("/");
  await openFolderFromMainWorkspace(page, rootTitle);
  // Create the folder structure
  await createFolderInCurrentFolder(page, "John");
  await createFolderInCurrentFolder(page, "Doe");
  await navigateToFolder(page, "Doe", getMainWorkspaceBreadcrumbs(rootTitle, "Doe"));
  await createFolderInCurrentFolder(page, "Jane");
  await navigateToFolder(
    page,
    "Jane",
    getMainWorkspaceBreadcrumbs(rootTitle, "Doe", "Jane"),
  );
  await createFolderInCurrentFolder(page, "Jim");

  // return to the isolated workspace root
  await openFolderFromMainWorkspace(page, rootTitle);

  // Search and select to move an item
  const JohnRow = await getRowItem(page, "John");

  await expect(JohnRow).toBeVisible();
  await clickOnRowItemActions(page, "John", "Move");
  await searchAndSelectItem(page, "Jim");
  const moveFolderModal = await getMoveFolderModal(page);
  await expectExplorerBreadcrumbs(moveFolderModal, [
    "My files",
    rootTitle,
    "Doe",
    "Jane",
    "Jim",
  ]);
  await acceptMoveItem(page);

  await openFolderFromMainWorkspace(page, rootTitle);
  await expectRowItemIsNotVisible(page, "John");
  await navigateToFolder(page, "Doe", getMainWorkspaceBreadcrumbs(rootTitle, "Doe"));
  await navigateToFolder(
    page,
    "Jane",
    getMainWorkspaceBreadcrumbs(rootTitle, "Doe", "Jane"),
  );
  await navigateToFolder(
    page,
    "Jim",
    getMainWorkspaceBreadcrumbs(rootTitle, "Doe", "Jane", "Jim"),
  );
  await expectRowItem(page, "John");
});

test("Move item to root", async ({ page, isolatedWorkspace, primaryActor }) => {
  const rootTitle = isolatedWorkspace.result.workspace_root.title;
  const apiBase = new URL(
    "/api/v1.0/",
    process.env.E2E_API_ORIGIN || "http://127.0.0.1:8071",
  ).toString();
  await page.goto("/");
  await openFolderFromMainWorkspace(page, rootTitle);
  // Create the folder structure
  await createFolderInCurrentFolder(page, "John");
  await navigateToFolder(page, "John", getMainWorkspaceBreadcrumbs(rootTitle, "John"));
  await createFolderInCurrentFolder(page, "Doe");
  await clickToMyFiles(page);
  await expectDefaultRoute(page, "My files", "/explorer/items/my-files");
  await expectRowItemIsNotVisible(page, "Doe");
  await openFolderFromMainWorkspace(page, rootTitle);
  await navigateToFolder(page, "John", getMainWorkspaceBreadcrumbs(rootTitle, "John"));
  await expectRowItem(page, "Doe");
  await clickOnRowItemActions(page, "Doe", "Move");
  await clickAndAcceptMoveToRoot(page);
  await expectRowItemIsNotVisible(page, "Doe");
  await clickToMyFiles(page);
  await expectDefaultRoute(page, "My files", "/explorer/items/my-files");
  const rootItemsResponse = await page.request.get(`${apiBase}items/`);
  expect(rootItemsResponse.ok()).toBeTruthy();
  const rootItems = (await rootItemsResponse.json()) as {
    results?: Array<{ id?: string; title?: string }>;
  };
  expect(
    rootItems.results?.some(
      (item) =>
        item.title === "Doe" && item.id && item.id !== primaryActor.workspace.id,
    ) ?? false,
  ).toBeTruthy();
});
