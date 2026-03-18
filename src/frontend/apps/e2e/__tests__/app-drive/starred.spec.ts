import { test } from "./fixtures/scenarios";
import {
  clickToFavorites,
  getMainWorkspaceBreadcrumbs,
  navigateToFolder,
  openFolderFromMainWorkspace,
} from "./utils-navigate";
import { createFolderInCurrentFolder } from "./utils-item";
import { expectRowItem } from "./utils-embedded-grid";
import {
  starItem,
  unstarItem,
  verifyItemIsNotStarred,
  verifyItemIsStarred,
} from "./utils/starred-utils";
import { clickOnBreadcrumbButtonAction } from "./utils-explorer";

test("Add an item to starred and verify it's displayed in the starred tree and page", async ({
  page,
  isolatedWorkspace,
}) => {
  const folderName = `testFolder-${isolatedWorkspace.scope.scenario_slug}`;
  await page.goto("/");
  await openFolderFromMainWorkspace(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );
  await createFolderInCurrentFolder(page, folderName);
  await starItem(page, folderName);
  await verifyItemIsStarred(page, folderName);
  await clickToFavorites(page);
  await expectRowItem(page, folderName);
});

test("Remove an item from starred and verify it's not displayed in the starred tree and page", async ({
  page,
  isolatedWorkspace,
}) => {
  const folderName = `testFolder-${isolatedWorkspace.scope.scenario_slug}`;
  await page.goto("/");
  await openFolderFromMainWorkspace(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );
  await createFolderInCurrentFolder(page, folderName);
  await starItem(page, folderName);
  await verifyItemIsStarred(page, folderName);
  await clickToFavorites(page);
  await expectRowItem(page, folderName);
  await openFolderFromMainWorkspace(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );
  await unstarItem(page, folderName);
  await verifyItemIsNotStarred(page, folderName);
});

test("Add an item to starred and one of it's children to starred and verify it's displayed in the starred tree and page", async ({
  page,
  isolatedWorkspace,
}) => {
  const rootTitle = isolatedWorkspace.result.workspace_root.title;
  const parentFolderName = `John-${isolatedWorkspace.scope.scenario_slug}`;
  const childFolderName = `Doe-${isolatedWorkspace.scope.scenario_slug}`;
  await page.goto("/");
  await openFolderFromMainWorkspace(page, rootTitle);
  await createFolderInCurrentFolder(page, parentFolderName);
  await navigateToFolder(
    page,
    parentFolderName,
    getMainWorkspaceBreadcrumbs(rootTitle, parentFolderName),
  );
  await createFolderInCurrentFolder(page, childFolderName);
  await clickOnBreadcrumbButtonAction(page, "Star");
  await starItem(page, childFolderName);
  await verifyItemIsStarred(page, parentFolderName);
  await verifyItemIsStarred(page, childFolderName, [parentFolderName]);
});
