import { expect, type Page } from "@playwright/test";
import { test } from "./fixtures/scenarios";
import { openFolderFromMainWorkspace } from "./utils-navigate";
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
import { getMountRow, openMountFixtureRoot } from "./utils-mounts";

const menuLabels = {
  createFolder: /^(Create folder|Créer un dossier)$/i,
  document: /^Document \(ODT\)$/i,
  presentation: /^Presentation \(ODP\)$/i,
  spreadsheet: /^Spreadsheet \(ODS\)$/i,
  moreFormats: /^(More formats\.\.\.|Plus de formats\.\.\.)$/i,
  importFiles: /^(Import files|Importer des fichiers)$/i,
  importFolders: /^(Import folders|Importer des dossiers)$/i,
  share: /^(Share|Partager)$/i,
  browse: /^(Browse|Parcourir)$/i,
  rename: /^(Rename|Renommer)$/i,
  move: /^(Move|Déplacer)$/i,
  info: /^(Information|Informations)$/i,
  delete: /^(Delete|Supprimer)$/i,
  star: /^(Star|Favoris)$/i,
  download: /^(Download|Télécharger)$/i,
  duplicate: /^(Duplicate|Dupliquer|Dupliceren)$/i,
} as const;

const buttonLabels = {
  create: /^(Create|Créer)$/i,
  rename: /^(Rename|Renommer)$/i,
} as const;

const fieldLabels = {
  newName: /^(New name|Nouveau nom)$/i,
} as const;

test.describe("Context menu", () => {
  test.beforeEach(async ({ page, isolatedWorkspace }) => {
    await page.goto("/");
    await openFolderFromMainWorkspace(
      page,
      isolatedWorkspace.result.workspace_root.title,
    );
  });

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
        page.getByRole("menuitem", { name: menuLabels.createFolder }),
      ).toBeVisible({ timeout: 5_000 });
    };

    try {
      await openAt(10, box.height - 10);
    } catch {
      await page.keyboard.press("Escape");
      await openAt(box.width - 10, box.height - 10);
    }
  };

  const expectMenuItemsInOrder = async (
    page: Page,
    labels: Array<string | RegExp>,
  ) => {
    const yPositions: number[] = [];

    for (const label of labels) {
      const item = page.getByRole("menuitem", { name: label });
      await expect(item).toBeVisible({ timeout: 5_000 });
      const box = await item.boundingBox();
      if (!box) {
        throw new Error(`menu item ${label} has no bounding box`);
      }
      yPositions.push(box.y);
    }

    expect(yPositions).toEqual([...yPositions].sort((a, b) => a - b));
  };

  // --- Background right-click ---

  test("Right-click on empty area shows create menu items", async ({
    page,
    isolatedWorkspace,
  }) => {
    await createFolderInCurrentFolder(
      page,
      `Placeholder-${isolatedWorkspace.scope.scenario_slug}`,
    );

    await rightClickOnExplorerEmptyArea(page);

    await expect(
      page.getByRole("menuitem", { name: menuLabels.createFolder }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.document }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.presentation }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.spreadsheet }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.moreFormats }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.importFiles }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.importFolders }),
    ).toBeVisible();
    await expectMenuItemsInOrder(page, [
      menuLabels.createFolder,
      menuLabels.importFiles,
      menuLabels.importFolders,
    ]);
  });

  test("Right-click on empty area > Create folder works", async ({
    page,
    isolatedWorkspace,
  }) => {
    await createFolderInCurrentFolder(
      page,
      `Placeholder-${isolatedWorkspace.scope.scenario_slug}`,
    );

    await rightClickOnExplorerEmptyArea(page);

    await page.getByRole("menuitem", { name: menuLabels.createFolder }).click();

    const folderName = `ContextMenuFolder-${isolatedWorkspace.scope.scenario_slug}`;
    await page.getByTestId("create-folder-input").fill(folderName);
    await page.getByRole("button", { name: buttonLabels.create }).click();

    await expectRowItem(page, folderName);
  });

  // --- Item right-click ---

  test("Right-click on item shows action menu items in the expected order", async ({
    page,
    isolatedWorkspace,
  }) => {
    const folderName = `TestFolder-${isolatedWorkspace.scope.scenario_slug}`;
    await createFolderInCurrentFolder(page, folderName);

    const row = await getRowItem(page, folderName);
    await row.click({ button: "right" });

    await expect(
      page.getByRole("menuitem", { name: menuLabels.info }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.share }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.move }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.rename }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.star }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.delete }),
    ).toBeVisible();
    await expectMenuItemsInOrder(page, [
      menuLabels.share,
      menuLabels.star,
      menuLabels.rename,
      menuLabels.move,
      menuLabels.info,
      menuLabels.delete,
    ]);
  });

  test("Right-click on item > Rename works", async ({
    page,
    isolatedWorkspace,
  }) => {
    const folderName = `TestFolder-${isolatedWorkspace.scope.scenario_slug}`;
    const renamed = `RenamedFolder-${isolatedWorkspace.scope.scenario_slug}`;
    await createFolderInCurrentFolder(page, folderName);

    const row = await getRowItem(page, folderName);
    await row.click({ button: "right" });
    await page.getByRole("menuitem", { name: menuLabels.rename }).click();

    await page
      .getByRole("textbox", { name: fieldLabels.newName })
      .fill(renamed);
    const renameResponse = page.waitForResponse(
      (response) => {
        const pathname = new URL(response.url()).pathname;
        return (
          response.request().method() === "PATCH" &&
          /\/api\/v1\.0\/items\/[^/]+\/$/.test(pathname) &&
          response.status() < 400
        );
      },
    );
    await page.getByRole("button", { name: buttonLabels.rename }).click();
    await renameResponse;

    await expectRowItem(page, renamed);
    await expectRowItemIsNotVisible(page, folderName);
  });

  test("Right-click on item > Delete works", async ({
    page,
    isolatedWorkspace,
  }) => {
    const folderName = `TestFolder-${isolatedWorkspace.scope.scenario_slug}`;
    await createFolderInCurrentFolder(page, folderName);

    const row = await getRowItem(page, folderName);
    await row.click({ button: "right" });
    await page.getByRole("menuitem", { name: menuLabels.delete }).click();

    await expectRowItemIsNotVisible(page, folderName);
  });

  test("Right-click on item > Star works", async ({
    page,
    isolatedWorkspace,
  }) => {
    const folderName = `TestFolder-${isolatedWorkspace.scope.scenario_slug}`;
    await createFolderInCurrentFolder(page, folderName);

    const row = await getRowItem(page, folderName);
    await row.click({ button: "right" });
    await page.getByRole("menuitem", { name: menuLabels.star }).click();

    await verifyItemIsStarred(page, folderName);
  });

  // --- File item right-click ---

  test("Right-click on file shows action menu items including Download in the expected order", async ({
    page,
    isolatedWorkspace,
  }) => {
    const fileName = `TestDoc-${isolatedWorkspace.scope.scenario_slug}`;
    const row = await createFileFromTemplate(page, fileName);
    await row.click({ button: "right" });

    await expect(
      page.getByRole("menuitem", { name: menuLabels.info }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.share }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.move }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.download }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.duplicate }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.rename }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.star }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.delete }),
    ).toBeVisible();
    await expectMenuItemsInOrder(page, [
      menuLabels.share,
      menuLabels.download,
      menuLabels.duplicate,
      menuLabels.star,
      menuLabels.rename,
      menuLabels.move,
      menuLabels.info,
      menuLabels.delete,
    ]);
  });

  test("Right-click on file > Share opens modal", async ({
    page,
    isolatedWorkspace,
  }) => {
    const fileName = `TestDoc-${isolatedWorkspace.scope.scenario_slug}`;
    const row = await createFileFromTemplate(page, fileName);
    await row.click({ button: "right" });
    await page.getByRole("menuitem", { name: menuLabels.share }).click();

    await expectShareModal(page);
  });

  test("Right-click on file > Move opens modal", async ({
    page,
    isolatedWorkspace,
  }) => {
    const fileName = `TestDoc-${isolatedWorkspace.scope.scenario_slug}`;
    const row = await createFileFromTemplate(page, fileName);
    await row.click({ button: "right" });
    await page.getByRole("menuitem", { name: menuLabels.move }).click();

    await expectMoveFolderModal(page);
  });

  test("Mount background and folder context menus converge the shared action order", async ({
    page,
    mountFixtureTree,
    primaryActor,
  }, testInfo) => {
    test.skip(
      process.env.E2E_ENABLE_MOUNTS !== "1",
      "Mounts E2E is disabled by default",
    );
    testInfo.setTimeout(90_000);

    await openMountFixtureRoot({
      page,
      primaryActor,
      mountFixtureTree,
    });

    await rightClickOnExplorerEmptyArea(page);
    await expect(
      page.getByRole("menuitem", { name: menuLabels.createFolder }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.importFiles }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.importFolders }),
    ).toBeVisible();
    await expectMenuItemsInOrder(page, [
      menuLabels.createFolder,
      menuLabels.importFiles,
      menuLabels.importFolders,
    ]);

    await page.keyboard.press("Escape");

    const row = getMountRow(page, "inbox");
    await row.click({ button: "right" });

    const shareItem = page.getByRole("menuitem", { name: menuLabels.share });
    const expectedMountActions = [
      menuLabels.browse,
      ...((await shareItem.isVisible().catch(() => false))
        ? [menuLabels.share]
        : []),
      menuLabels.rename,
      menuLabels.move,
      menuLabels.info,
      menuLabels.delete,
    ];

    await expect(
      page.getByRole("menuitem", { name: menuLabels.browse }),
    ).toBeVisible();
    if (expectedMountActions.includes(menuLabels.share)) {
      await expect(shareItem).toBeVisible();
    } else {
      await expect(shareItem).toBeHidden();
    }
    await expect(
      page.getByRole("menuitem", { name: menuLabels.rename }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.move }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.info }),
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: menuLabels.delete }),
    ).toBeVisible();
    await expectMenuItemsInOrder(page, expectedMountActions);
  });
});
