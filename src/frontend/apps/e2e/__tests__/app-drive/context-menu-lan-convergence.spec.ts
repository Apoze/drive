import { expect, Page } from "@playwright/test";
import { test } from "./fixtures/actors";
import { dismissReleaseNotesIfPresent } from "./utils-common";
import {
  createFolderInCurrentFolder,
} from "./utils-item";
import {
  expectExplorerShellReady,
  gotoExplorerRoute,
} from "./utils-explorer";
import {
  expectRowItem,
  getRowItem,
} from "./utils-embedded-grid";
import { getMountRow } from "./utils-mounts";
import { openMainWorkspaceFromMyFiles } from "./utils-navigate";

const menuLabels = {
  createFolder: /^(Create folder|Créer un dossier)$/i,
  importFiles: /^(Import files|Importer des fichiers)$/i,
  importFolders: /^(Import folders|Importer des dossiers)$/i,
  share: /^(Share|Partager)$/i,
  browse: /^(Browse|Parcourir)$/i,
  rename: /^(Rename|Renommer)$/i,
  move: /^(Move|Déplacer)$/i,
  info: /^(Information|Informations)$/i,
  delete: /^(Delete|Supprimer)$/i,
  star: /^(Star|Favoris)$/i,
} as const;

const buttonLabels = {
  create: /^(Create|Créer)$/i,
} as const;

const rightClickOnExplorerEmptyArea = async (page: Page) => {
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
      throw new Error(`menu item ${String(label)} has no bounding box`);
    }
    yPositions.push(box.y);
  }

  expect(yPositions).toEqual([...yPositions].sort((a, b) => a - b));
};

const resolveInteractiveMount = async (page: Page) => {
  const apiOrigin = process.env.E2E_API_ORIGIN || "http://192.168.10.123:8071";
  return page.evaluate(async (resolvedApiOrigin) => {
    const mountsResponse = await fetch(`${resolvedApiOrigin}/api/v1.0/mounts/`, {
      credentials: "include",
    });
    if (!mountsResponse.ok) {
      throw new Error(`mounts discovery failed: ${mountsResponse.status}`);
    }

    const mounts = (await mountsResponse.json()) as Array<{ mount_id: string }>;

    for (const mount of mounts) {
      const browseResponse = await fetch(
        `${resolvedApiOrigin}/api/v1.0/mounts/${mount.mount_id}/browse/?path=/`,
        {
          credentials: "include",
        },
      );
      if (!browseResponse.ok) {
        continue;
      }
      const browse = (await browseResponse.json()) as {
        capabilities?: Record<string, boolean>;
        entry?: {
          abilities?: Record<string, boolean>;
        };
      };

      if (
        browse.capabilities?.["mount.upload"] &&
        browse.capabilities?.["mount.create_folder"] &&
        browse.entry?.abilities?.upload &&
        browse.entry?.abilities?.create_folder
      ) {
        return {
          mountId: mount.mount_id,
          canShareLink: Boolean(browse.capabilities?.["mount.share_link"]),
        };
      }
    }

    return null;
  }, apiOrigin);
};

test.setTimeout(90_000);

test("Items and mounts converge shared context-menu and shell action order on LAN", async ({
  page,
}) => {
  const stamp = Date.now();
  const itemFolderName = `Context menu item ${stamp}`;
  const mountFolderName = `00 Context menu mount ${stamp}`;

  await page.goto("/");
  await dismissReleaseNotesIfPresent(page, 10_000);

  await openMainWorkspaceFromMyFiles(page);
  await createFolderInCurrentFolder(page, itemFolderName);
  await expectRowItem(page, itemFolderName);

  const itemRow = await getRowItem(page, itemFolderName);
  await itemRow.click({ button: "right" });
  await expectMenuItemsInOrder(page, [
    menuLabels.share,
    menuLabels.star,
    menuLabels.rename,
    menuLabels.move,
    menuLabels.info,
    menuLabels.delete,
  ]);
  await page.keyboard.press("Escape");
  await itemRow.dblclick();
  await expectExplorerShellReady(page);
  await expect(page.getByTestId("explorer-breadcrumbs")).toContainText(
    itemFolderName,
  );

  await rightClickOnExplorerEmptyArea(page);
  await expectMenuItemsInOrder(page, [
    menuLabels.createFolder,
    menuLabels.importFiles,
    menuLabels.importFolders,
  ]);
  await page.keyboard.press("Escape");

  const mountTarget = await resolveInteractiveMount(page);
  expect(mountTarget).toBeTruthy();

  await gotoExplorerRoute(page, `/explorer/mounts/${mountTarget!.mountId}`);
  await dismissReleaseNotesIfPresent(page, 10_000);
  await expectExplorerShellReady(page);
  await page.getByTestId("mount-create-folder-button").click();

  const createDialog = page.getByRole("dialog").last();
  await createDialog.getByRole("textbox").fill(mountFolderName);
  await createDialog.getByRole("button", { name: buttonLabels.create }).click();
  await expect(getMountRow(page, mountFolderName)).toBeVisible({ timeout: 20_000 });

  const mountRow = getMountRow(page, mountFolderName);
  await mountRow.click({ button: "right" });
  const mountMenuOrder = [menuLabels.browse];
  if (mountTarget!.canShareLink) {
    mountMenuOrder.push(menuLabels.share);
  }
  mountMenuOrder.push(
    menuLabels.rename,
    menuLabels.move,
    menuLabels.info,
    menuLabels.delete,
  );
  await expectMenuItemsInOrder(page, mountMenuOrder);
  await page.keyboard.press("Escape");
  await mountRow.dblclick();
  await expectExplorerShellReady(page);
  await expect(page.getByTestId("explorer-breadcrumbs")).toContainText(
    mountFolderName,
  );

  await rightClickOnExplorerEmptyArea(page);
  await expectMenuItemsInOrder(page, [
    menuLabels.createFolder,
    menuLabels.importFiles,
    menuLabels.importFolders,
  ]);
});
