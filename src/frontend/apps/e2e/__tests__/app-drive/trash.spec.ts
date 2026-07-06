import { expect, Page } from "@playwright/test";
import { test } from "./fixtures/scenarios";
import {
  clickOnRowItemActions,
  expectRowItem,
  expectRowItemIsNotVisible,
  getRowItem,
} from "./utils-embedded-grid";
import {
  createFileFromTemplate,
  createFolderInCurrentFolder,
} from "./utils-item";
import { gotoExplorerRoute } from "./utils-explorer";
import { openFolderFromMainWorkspace } from "./utils-navigate";

const DELETE_ACTION = /^(Delete|Supprimer|Verwijderen)$/i;
const DELETE_FOREVER_ACTION =
  /^(Delete forever|Supprimer définitivement|Verwijder permanent)$/i;

const getTrashRow = (page: Page, itemName: string) =>
  page.locator("tr.selectable").filter({
    has: page.getByRole("button", {
      name: itemName,
      exact: true,
    }),
  });

const openIsolatedWorkspace = async (
  page: Page,
  isolatedWorkspaceTitle: string,
) => {
  await page.goto("/");
  await openFolderFromMainWorkspace(page, isolatedWorkspaceTitle);
};

const goToTrash = async (page: Page) => {
  await gotoExplorerRoute(page, "/explorer/trash");
  const breadcrumbs = page.getByTestId("trash-page-breadcrumbs");
  await expect(breadcrumbs).toBeVisible({ timeout: 20_000 });
  await expect(breadcrumbs).toContainText("Trash");
};

const moveItemToTrash = async (page: Page, itemName: string) => {
  await clickOnRowItemActions(page, itemName, DELETE_ACTION);
  await goToTrash(page);
  await expectRowItem(page, itemName);
};

const deleteItemFromCurrentFolder = async (page: Page, itemName: string) => {
  await clickOnRowItemActions(page, itemName, DELETE_ACTION);
  await expectRowItemIsNotVisible(page, itemName, { timeoutMs: 30_000 });
};

const confirmDeleteForever = async (page: Page) => {
  const dialog = page.getByRole("dialog").filter({
    has: page.getByRole("button", { name: DELETE_FOREVER_ACTION }),
  });
  await dialog
    .getByRole("button", { name: DELETE_FOREVER_ACTION })
    .last()
    .click();
};

test.setTimeout(90_000);

test("Hard deleting an item from trash row actions refreshes the list", async ({
  page,
  isolatedWorkspace,
}) => {
  const folderName = `Folder hard delete row ${Date.now()}`;

  await openIsolatedWorkspace(page, isolatedWorkspace.result.workspace_root.title);
  await createFolderInCurrentFolder(page, folderName);
  await moveItemToTrash(page, folderName);

  const row = getTrashRow(page, folderName);
  await row.getByRole("button").last().click();
  await page.getByRole("menuitem", { name: DELETE_FOREVER_ACTION }).click();
  await confirmDeleteForever(page);

  await expectRowItemIsNotVisible(page, folderName, { timeoutMs: 30_000 });
});

test("Hard deleting an item from the trash selection bar refreshes the list", async ({
  page,
  isolatedWorkspace,
}) => {
  const folderName = `Folder hard delete bar ${Date.now()}`;

  await openIsolatedWorkspace(page, isolatedWorkspace.result.workspace_root.title);
  await createFolderInCurrentFolder(page, folderName);
  await moveItemToTrash(page, folderName);

  const row = getTrashRow(page, folderName);
  await row.click({ modifiers: ["ControlOrMeta"], force: true });

  const selectionBar = page.locator(".explorer__selection-bar");
  await expect(selectionBar).toBeVisible({ timeout: 20_000 });
  await selectionBar
    .getByRole("button", { name: DELETE_FOREVER_ACTION })
    .click();
  await confirmDeleteForever(page);

  await expectRowItemIsNotVisible(page, folderName, { timeoutMs: 30_000 });
});

test("Clicking deleted folders and files shows trash information modals", async ({
  page,
  isolatedWorkspace,
}) => {
  const stamp = Date.now();
  const folderName = `Folder in trash ${stamp}`;
  const fileBaseName = `File in trash ${stamp}`;
  const fileName = `${fileBaseName}.odt`;

  await openIsolatedWorkspace(page, isolatedWorkspace.result.workspace_root.title);
  await createFolderInCurrentFolder(page, folderName);
  await createFileFromTemplate(page, fileBaseName);
  await deleteItemFromCurrentFolder(page, folderName);
  await deleteItemFromCurrentFolder(page, fileName);
  await goToTrash(page);
  await expectRowItem(page, folderName);
  await expectRowItem(page, fileName);

  const folderButton = await getRowItem(page, folderName);
  await folderButton.dblclick({ force: true });
  await expect(page.getByText("This folder is in the trash")).toBeVisible();
  await expect(
    page.getByText("To display this folder, you need to restore it first."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Ok" }).click();
  await expect.poll(() => page.url(), { timeout: 20_000 }).toContain("/explorer/trash");

  const fileButton = await getRowItem(page, fileName);
  await fileButton.dblclick({ force: true });
  await expect(page.getByText("This file is in the trash")).toBeVisible();
  await expect(
    page.getByText("To display this file, you need to restore it first."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Ok" }).click();
  await expect.poll(() => page.url(), { timeout: 20_000 }).toContain("/explorer/trash");
});
