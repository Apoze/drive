import test, { expect, type Page } from "@playwright/test";
import { clearDb, login } from "./utils-common";
import { clickToMyFiles } from "./utils-navigate";
import {
  createFileFromTemplate,
  createFolderInCurrentFolder,
} from "./utils-item";
import {
  expectRowItem,
  expectRowItemIsNotVisible,
  getRowItem,
} from "./utils-embedded-grid";
import { verifyItemIsStarred } from "./utils/starred-utils";
import { expectShareModal } from "./utils/share-utils";
import { expectMoveFolderModal } from "./utils/move-utils";

test.describe("Context menu", () => {
  test.beforeEach(async ({ page }) => {
    await clearDb();
    await login(page, "drive@example.com");
    await page.goto("/");
    await clickToMyFiles(page);
  });

  const uniqueName = (prefix: string) =>
    `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`;

  const rightClickOnExplorerEmptyArea = async (page: Page) => {
    // Ensure we right-click on a true "background" target (not a row item),
    // otherwise the item context menu takes precedence.
    await page.keyboard.press("Escape");
    const gridContainer = page.locator(".explorer__grid__container");
    const box = await gridContainer.boundingBox();
    if (!box) {
      throw new Error("explorer grid container not visible");
    }
    const openAt = async (dx: number, dy: number) => {
      await page.mouse.click(box.x + dx, box.y + dy, { button: "right" });
      await expect(
        page.getByRole("menuitem", { name: /Create folder/i }),
      ).toBeVisible({ timeout: 5_000 });
    };

    try {
      await openAt(10, box.height - 10);
    } catch {
      await page.keyboard.press("Escape");
      await openAt(box.width - 10, box.height - 10);
    }
  };

  // --- Background right-click ---

  test("Right-click on empty area shows create menu items", async ({
    page,
  }) => {
    await createFolderInCurrentFolder(page, uniqueName("Placeholder"));

    await rightClickOnExplorerEmptyArea(page);

    await expect(
      page.getByRole("menuitem", { name: /Create folder/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: "Document (ODT)" }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: "Presentation (ODP)" }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: "Spreadsheet (ODS)" }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: "More formats..." }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: "Import files" }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: "Import folders" }),
    ).toBeVisible();
  });

  test("Right-click on empty area > Create folder works", async ({ page }) => {
    await createFolderInCurrentFolder(page, uniqueName("Placeholder"));

    await rightClickOnExplorerEmptyArea(page);

    await page.getByRole("menuitem", { name: /Create folder/i }).click();

    const folderName = uniqueName("ContextMenuFolder");
    await page.getByTestId("create-folder-input").fill(folderName);
    await page.getByRole("button", { name: "Create" }).click();

    await expectRowItem(page, folderName);
  });

  // --- Item right-click ---

  test("Right-click on item shows action menu items", async ({ page }) => {
    const folderName = uniqueName("TestFolder");
    await createFolderInCurrentFolder(page, folderName);

    const row = await getRowItem(page, folderName);
    await row.click({ button: "right" });

    await expect(
      page.getByRole("menuitem", { name: "Information" }),
    ).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Share" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Move" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Rename" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Star" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Delete" })).toBeVisible();
  });

  test("Right-click on item > Rename works", async ({ page }) => {
    const folderName = uniqueName("TestFolder");
    const renamed = uniqueName("RenamedFolder");
    await createFolderInCurrentFolder(page, folderName);

    const row = await getRowItem(page, folderName);
    await row.click({ button: "right" });
    await page.getByRole("menuitem", { name: "Rename" }).click();

    await page.getByRole("textbox", { name: "New name" }).fill(renamed);
    await page.getByRole("button", { name: "Rename" }).click();

    await expectRowItem(page, renamed);
    await expectRowItemIsNotVisible(page, folderName);
  });

  test("Right-click on item > Delete works", async ({ page }) => {
    const folderName = uniqueName("TestFolder");
    await createFolderInCurrentFolder(page, folderName);

    const row = await getRowItem(page, folderName);
    await row.click({ button: "right" });
    await page.getByRole("menuitem", { name: "Delete" }).click();

    await expectRowItemIsNotVisible(page, folderName);
  });

  test("Right-click on item > Star works", async ({ page }) => {
    const folderName = uniqueName("TestFolder");
    await createFolderInCurrentFolder(page, folderName);

    const row = await getRowItem(page, folderName);
    await row.click({ button: "right" });
    await page.getByRole("menuitem", { name: "Star" }).click();

    await verifyItemIsStarred(page, folderName);
  });

  // --- File item right-click ---

  test("Right-click on file shows action menu items including Download", async ({
    page,
  }) => {
    const fileName = uniqueName("TestDoc");
    const row = await createFileFromTemplate(page, fileName);
    await row.click({ button: "right" });

    await expect(
      page.getByRole("menuitem", { name: "Information" }),
    ).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Share" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Move" })).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: "Download" }),
    ).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Rename" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Star" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Delete" })).toBeVisible();
  });

  test("Right-click on file > Share opens modal", async ({ page }) => {
    const fileName = uniqueName("TestDoc");
    const row = await createFileFromTemplate(page, fileName);
    await row.click({ button: "right" });
    await page.getByRole("menuitem", { name: "Share" }).click();

    await expectShareModal(page);
  });

  test("Right-click on file > Move opens modal", async ({ page }) => {
    const fileName = uniqueName("TestDoc");
    const row = await createFileFromTemplate(page, fileName);
    await row.click({ button: "right" });
    await page.getByRole("menuitem", { name: "Move" }).click();

    await expectMoveFolderModal(page);
  });
});
