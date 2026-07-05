import { expect } from "@playwright/test";
import { test } from "./fixtures/scenarios";
import { createFolderInCurrentFolder, deleteCurrentFolder } from "./utils-item";
import {
  expectExplorerBreadcrumbs,
  expectExplorerRouteReady,
} from "./utils-explorer";
import {
  getMainWorkspaceBreadcrumbs,
  navigateToFolder,
  openFolderFromMainWorkspace,
} from "./utils-navigate";

test("Checks that if one of the parents of the current folder is deleted, it redirects to the highest parent", async ({
  page,
  isolatedWorkspace,
}) => {
  const rootTitle = isolatedWorkspace.result.workspace_root.title;
  await page.goto("/");
  await openFolderFromMainWorkspace(page, rootTitle);
  await createFolderInCurrentFolder(page, "Test");
  await navigateToFolder(page, "Test", getMainWorkspaceBreadcrumbs(rootTitle, "Test"));
  const testUrl = page.url();
  await createFolderInCurrentFolder(page, "SubTest");
  await navigateToFolder(
    page,
    "SubTest",
    getMainWorkspaceBreadcrumbs(rootTitle, "Test", "SubTest"),
  );
  await deleteCurrentFolder(page);
  await expectExplorerRouteReady(page, new URL(testUrl).pathname);
  await expectExplorerBreadcrumbs(
    page,
    getMainWorkspaceBreadcrumbs(rootTitle, "Test"),
  );
});

test("Check that if we delete the current folder, it redirects to the parent folder", async ({
  page,
  isolatedWorkspace,
}) => {
  const rootTitle = isolatedWorkspace.result.workspace_root.title;
  await page.goto("/");
  await openFolderFromMainWorkspace(page, rootTitle);
  const parentUrl = page.url();
  await createFolderInCurrentFolder(page, "Test");
  await navigateToFolder(page, "Test", getMainWorkspaceBreadcrumbs(rootTitle, "Test"));
  await deleteCurrentFolder(page);
  await expectExplorerRouteReady(page, new URL(parentUrl).pathname);
  await expectExplorerBreadcrumbs(page, getMainWorkspaceBreadcrumbs(rootTitle));
});
