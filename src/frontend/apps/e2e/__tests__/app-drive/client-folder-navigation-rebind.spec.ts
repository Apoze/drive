import { expect, Page } from "@playwright/test";
import { test } from "./fixtures/actors";
import { dismissReleaseNotesIfPresent } from "./utils-common";
import {
  expectRowItem,
  expectRowItemIsNotVisible,
  getRowItem,
  waitForExplorerGridToSettle,
} from "./utils-embedded-grid";
import { expectExplorerBreadcrumbs, expectExplorerShellReady } from "./utils-explorer";
import { createFolderInCurrentFolder } from "./utils-item";
import { starItem } from "./utils/starred-utils";
import { clickOnItemInTree, openTreeNode } from "./utils-tree";

test.setTimeout(90_000);

const expectFolderNavigationUrlChange = async ({
  page,
  previousUrl,
}: {
  page: Page;
  previousUrl: string;
}) => {
  await expect
    .poll(() => page.url(), { timeout: 20_000 })
    .not.toBe(previousUrl);
  await expect
    .poll(() => page.url(), { timeout: 20_000 })
    .toMatch(/\/explorer\/items\/[0-9a-f-]{36}(?:$|[?#/])/);
};

test("Grid and tree folder navigation rebind the explorer without a manual refresh", async ({
  page,
}) => {
  const myFilesLabel = "My files";
  const favoritesLabel = "Starred";
  const runSuffix = `${Date.now()}`;
  const workspaceRootTitle = `Codex nav root ${runSuffix}`;
  const alphaTitle = `Alpha ${runSuffix}`;
  const betaTitle = `Beta ${runSuffix}`;
  const alphaChildTitle = `Alpha child ${runSuffix}`;
  const betaChildTitle = `Beta child ${runSuffix}`;

  await page.goto("/");
  await dismissReleaseNotesIfPresent(page, 10_000);
  await expectExplorerShellReady(page);

  if (!/\/explorer\/items\/my-files(?:$|[?#/])/.test(page.url())) {
    const myFilesEntry = page
      .getByRole("link", { name: /my files|mes fichiers/i })
      .or(page.getByRole("button", { name: /my files|mes fichiers/i }))
      .first();
    await myFilesEntry.click({ noWaitAfter: true });
  }
  await expect
    .poll(() => page.url(), { timeout: 20_000 })
    .toMatch(/\/explorer\/items\/my-files(?:$|[?#/])/);
  await expectExplorerBreadcrumbs(page, [myFilesLabel]);

  await createFolderInCurrentFolder(page, workspaceRootTitle);
  const workspaceRootRow = await getRowItem(page, workspaceRootTitle);
  const myFilesUrl = page.url();
  const workspaceRootItemRequest = page.waitForResponse(
    (response) =>
      /\/api\/v1\.0\/items\/[0-9a-f-]{36}\/$/.test(new URL(response.url()).pathname) &&
      response.request().method() === "GET",
    { timeout: 10_000 },
  ).catch(() => null);
  await workspaceRootRow.dblclick();
  await expectFolderNavigationUrlChange({ page, previousUrl: myFilesUrl });
  await dismissReleaseNotesIfPresent(page);
  const workspaceRootItemResponse = await workspaceRootItemRequest;
  expect(workspaceRootItemResponse?.ok()).toBeTruthy();
  await expectExplorerBreadcrumbs(page, [myFilesLabel, workspaceRootTitle]);

  await createFolderInCurrentFolder(page, alphaTitle);
  await createFolderInCurrentFolder(page, betaTitle);
  await expectRowItem(page, alphaTitle);
  await expectRowItem(page, betaTitle);

  const alphaRow = await getRowItem(page, alphaTitle);
  const workspaceUrl = page.url();
  await alphaRow.dblclick();
  await expectFolderNavigationUrlChange({ page, previousUrl: workspaceUrl });
  await dismissReleaseNotesIfPresent(page);
  await expectExplorerBreadcrumbs(page, [myFilesLabel, workspaceRootTitle, alphaTitle]);
  await createFolderInCurrentFolder(page, alphaChildTitle);
  await expectRowItem(page, alphaChildTitle);

  await page
    .getByTestId("explorer-breadcrumbs")
    .getByRole("button", { name: workspaceRootTitle, exact: true })
    .click();
  await expect
    .poll(() => page.url(), { timeout: 20_000 })
    .toBe(workspaceUrl);
  await waitForExplorerGridToSettle(page);
  await expectExplorerBreadcrumbs(page, [myFilesLabel, workspaceRootTitle]);

  const betaRow = await getRowItem(page, betaTitle);
  await betaRow.dblclick();
  await expectFolderNavigationUrlChange({ page, previousUrl: workspaceUrl });
  await dismissReleaseNotesIfPresent(page);
  await expectExplorerBreadcrumbs(page, [myFilesLabel, workspaceRootTitle, betaTitle]);
  await createFolderInCurrentFolder(page, betaChildTitle);
  await expectRowItem(page, betaChildTitle);

  await page
    .getByTestId("explorer-breadcrumbs")
    .getByRole("button", { name: workspaceRootTitle, exact: true })
    .click();
  await expect
    .poll(() => page.url(), { timeout: 20_000 })
    .toBe(workspaceUrl);
  await waitForExplorerGridToSettle(page);
  await expectExplorerBreadcrumbs(page, [myFilesLabel, workspaceRootTitle]);

  const alphaGridRow = await getRowItem(page, alphaTitle);
  await alphaGridRow.dblclick();
  await expectFolderNavigationUrlChange({ page, previousUrl: workspaceUrl });
  await dismissReleaseNotesIfPresent(page);
  await expectExplorerBreadcrumbs(page, [myFilesLabel, workspaceRootTitle, alphaTitle]);
  await expectRowItem(page, alphaChildTitle);
  await expectRowItemIsNotVisible(page, betaChildTitle);

  await page
    .getByTestId("explorer-breadcrumbs")
    .getByRole("button", { name: workspaceRootTitle, exact: true })
    .click();
  await expect
    .poll(() => page.url(), { timeout: 20_000 })
    .toBe(workspaceUrl);
  await waitForExplorerGridToSettle(page);
  await expectExplorerBreadcrumbs(page, [myFilesLabel, workspaceRootTitle]);

  await starItem(page, betaTitle);
  await openTreeNode(page, "Starred");
  await clickOnItemInTree(page, betaTitle);
  await expectFolderNavigationUrlChange({ page, previousUrl: workspaceUrl });
  await dismissReleaseNotesIfPresent(page);
  await expectExplorerBreadcrumbs(page, [favoritesLabel, workspaceRootTitle, betaTitle]);
  await expectRowItem(page, betaChildTitle);
  await expectRowItemIsNotVisible(page, alphaChildTitle);
});
