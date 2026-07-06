import { expect, Page } from "@playwright/test";
import { getRowItem, waitForExplorerGridToSettle } from "./utils-embedded-grid";
import { dismissReleaseNotesIfPresent } from "./utils-common";
import {
  clickOnBreadcrumbButtonAction,
  expectExplorerRouteReady,
} from "./utils-explorer";
import { closeFilePreview } from "./utils-editor";

export const createFolder = async (page: Page, folderName: string) => {
  await page.getByRole("button", { name: "Create Folder" }).click();
  await page.getByRole("textbox", { name: "Folder name" }).click();
  await page.getByRole("textbox", { name: "Folder name" }).fill(folderName);
  await page.getByRole("button", { name: /create|créer/i }).click();
};

export const createFolderInCurrentFolder = async (
  page: Page,
  folderName: string,
) => {
  await dismissReleaseNotesIfPresent(page);
  await waitForExplorerGridToSettle(page);
  const createFolderInput = page.getByTestId("create-folder-input");
  const createFolderDialog = page
    .getByRole("dialog")
    .filter({ has: createFolderInput })
    .first();
  const explorerBreadcrumbs = page.getByTestId("explorer-breadcrumbs");
  const createFolderButton = page.getByTestId("create-folder-button");

  await page.getByTestId("create-folder-button").click();
  await createFolderInput.click();
  await createFolderInput.fill(folderName);
  const createFolderResponse = page.waitForResponse((response) => {
    const request = response.request();
    return (
      request.method() === "POST" &&
      response.url().includes("/api/v1.0/items/") &&
      response.status() >= 200 &&
      response.status() < 300
    );
  });
  await page.getByRole("button", { name: /create|créer/i }).click();
  await createFolderResponse;

  // WebKit can return to the explorer before the grid has refreshed its rows.
  // Wait for the modal to close and the grid surface to become interactive again.
  try {
    await expect(createFolderInput).toBeHidden({ timeout: 20_000 });
  } catch {
    await expect(createFolderDialog).toBeHidden({ timeout: 20_000 });
  }
  await expect(explorerBreadcrumbs).toBeVisible({ timeout: 20_000 });
  await expect(createFolderButton).toBeVisible({ timeout: 20_000 });

  try {
    const folderItem = await getRowItem(page, folderName);
    await expect(folderItem).toBeVisible();
    return folderItem;
  } catch {
    const currentRoute = new URL(page.url()).pathname;
    await expect(explorerBreadcrumbs).toBeVisible({ timeout: 20_000 });
    await expect(createFolderButton).toBeVisible({ timeout: 20_000 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expectExplorerRouteReady(page, currentRoute);
    await waitForExplorerGridToSettle(page, 30_000);
    const folderItem = page
      .getByRole("button", { name: folderName, exact: true })
      .last();
    await expect
      .poll(async () => folderItem.isVisible().catch(() => false), {
        timeout: 30_000,
      })
      .toBe(true);
    return folderItem;
  }
};

export const createFileFromTemplate = async (
  page: Page,
  fileName: string,
  template: "Document (ODT)" | "Spreadsheet (ODS)" | "Presentation (ODP)" = "Document (ODT)",
) => {
  await waitForExplorerGridToSettle(page);
  // Use the explorer background context menu (stable across UI variations).
  await page.keyboard.press("Escape");
  const gridContainer = page.locator(".explorer__grid__container");
  const box = await gridContainer.boundingBox();
  if (!box) {
    throw new Error("explorer grid container not visible");
  }
  const tryRightClick = async (dx: number, dy: number) => {
    await page.mouse.click(box.x + dx, box.y + dy, { button: "right" });
    try {
      await expect(
        page.getByRole("menuitem", { name: /Create folder/i }),
      ).toBeVisible({ timeout: 5_000 });
      return true;
    } catch {
      return false;
    }
  };

  // Prefer clicking on an empty area; fall back to a second position if needed.
  if (!(await tryRightClick(10, box.height - 10))) {
    await page.keyboard.press("Escape");
    await tryRightClick(box.width - 10, box.height - 10);
  }
  if (!(await page.getByRole("menuitem", { name: /Create folder/i }).isVisible().catch(() => false))) {
    await page.keyboard.press("Escape");
    await tryRightClick(box.width - 10, box.height - 10);
  }

  await page.getByRole("menuitem", { name: template }).click();
  const createDialog = page.getByRole("dialog", { name: /^Create /i });
  const fileNameInput = createDialog.getByRole("textbox").first();
  await expect(fileNameInput).toBeVisible({ timeout: 20_000 });
  await fileNameInput.fill(fileName);
  await createDialog.getByRole("button", { name: "Create" }).click();
  await expect(createDialog).not.toBeVisible({ timeout: 20_000 });
  const extension =
    template === "Spreadsheet (ODS)"
      ? ".ods"
      : template === "Presentation (ODP)"
        ? ".odp"
        : ".odt";
  const fileDisplayName = `${fileName}${extension}`;

  // WebKit can open the freshly created file preview slightly after the create
  // dialog closes. Close it whenever it appears, then wait until the grid row is
  // visible again before returning the row locator.
  const filePreview = page.getByTestId("file-preview");
  const openedFileDialog = page
    .getByRole("dialog")
    .filter({ has: page.getByRole("heading", { name: fileDisplayName }) })
    .first();
  const fileRow = page
    .getByRole("button", { name: fileDisplayName, exact: true })
    .last();

  const closeFreshPreviewIfOpen = async () => {
    if (await filePreview.isVisible().catch(() => false)) {
      await closeFilePreview(page);
      return;
    }

    if (await openedFileDialog.isVisible().catch(() => false)) {
      await openedFileDialog
        .getByRole("button", { name: /^close$/i })
        .first()
        .click();
      await expect(openedFileDialog).toBeHidden({ timeout: 20_000 });
    }
  };

  await expect
    .poll(
      async () => {
        await closeFreshPreviewIfOpen();
        return fileRow.isVisible().catch(() => false);
      },
      { timeout: 30_000 },
    )
    .toBe(true);

  const fileItem = await getRowItem(page, fileDisplayName);
  await expect(fileItem).toBeVisible({ timeout: 30_000 });
  return fileItem;
};

export const importFile = async (page: Page, filePath: string) => {
  await waitForExplorerGridToSettle(page);
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Import" }).click();
  await page.getByRole("menuitem", { name: "Import files" }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(filePath);
};

export const deleteCurrentFolder = async (page: Page) => {
  const resetSelectionButton = page.getByRole("button", {
    name: /^(Reset selection|Réinitialiser la sélection)$/i,
  });
  if (await resetSelectionButton.isVisible().catch(() => false)) {
    await resetSelectionButton.click();
    await expect(page.locator(".explorer__selection-bar")).toBeHidden({
      timeout: 20_000,
    });
  }
  await clickOnBreadcrumbButtonAction(page, "Delete", {
    skipSelectionBar: true,
  });
};
