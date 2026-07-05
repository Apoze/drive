import path from "path";
import { expect, type Page } from "@playwright/test";

import type { MountFixtureTree, WorkerActorFixture } from "./fixtures/types";
import { dismissReleaseNotesIfPresent, ensureBootstrappedActorSession } from "./utils-common";

export const buildMountRoute = (mountId: string, normalizedPath: string) => {
  const query = normalizedPath && normalizedPath !== "/"
    ? `?path=${encodeURIComponent(normalizedPath)}`
    : "";
  return `/explorer/mounts/${mountId}${query}`;
};

export const closeMountFeedbackDialogIfPresent = async (page: Page) => {
  const dialog = page.getByRole("dialog", { name: "New feedback" });
  if ((await dialog.count()) === 0) return;
  const close = dialog.getByRole("button", { name: "close" });
  if (await close.isVisible().catch(() => false)) {
    await close.click();
  }
};

export const openMountFixtureRoot = async ({
  page,
  primaryActor,
  mountFixtureTree,
}: {
  page: Page;
  primaryActor: WorkerActorFixture;
  mountFixtureTree: MountFixtureTree;
}) => {
  await ensureBootstrappedActorSession(page, primaryActor);
  const mountUrl = buildMountRoute(
    mountFixtureTree.result.mount_id,
    mountFixtureTree.result.root_path,
  );
  await page.goto(mountUrl, { waitUntil: "commit" }).catch(() => undefined);
  await dismissReleaseNotesIfPresent(page);
  await closeMountFeedbackDialogIfPresent(page);
  await expect.poll(() => page.url(), { timeout: 20_000 }).toContain(
    `/explorer/mounts/${mountFixtureTree.result.mount_id}`,
  );
  await expect(
    page.getByRole("button", { name: /^(Import|Upload|Importer)$/i }),
  ).toBeVisible({
    timeout: 20_000,
  });
  return mountUrl;
};

export const getMountExplorerTable = (page: Page) =>
  page
    .getByRole("table")
    .filter({ has: page.getByRole("columnheader", { name: /^(Name|Nom)$/i }) })
    .or(page.getByRole("table").filter({ has: page.getByRole("cell", { name: /^(Name|Nom)$/i }) }))
    .first();

export const getMountRow = (page: Page, itemName: string) => {
  const escapedName = itemName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return getMountExplorerTable(page)
    .getByRole("row", { name: new RegExp(escapedName) })
    .first();
};

export const uploadFilesToCurrentMountFolder = async (page: Page, files: string[]) => {
  for (const file of files) {
    await page
      .getByRole("button", { name: /^(Import|Upload|Importer)$/i })
      .click();
    const importFilesItem = page.getByRole("menuitem", {
      name: /^(Import files|Importer des fichiers)$/i,
    });
    await expect(importFilesItem).toBeVisible({ timeout: 5_000 });
    const fileChooserPromise = page.waitForEvent("filechooser");
    await importFilesItem.click();
    const chooser = await fileChooserPromise;
    await chooser.setFiles([file]);
    await expect(getMountRow(page, path.basename(file))).toBeVisible({
      timeout: 20_000,
    });
  }
};

export const openMountFilePreview = async (page: Page, itemName: string) => {
  const row = getMountRow(page, itemName);
  await expect(row).toBeVisible({ timeout: 20_000 });
  const filePreview = page.getByTestId("file-preview");

  await row.evaluate((element) => {
    element.dispatchEvent(
      new MouseEvent("click", {
        bubbles: true,
        cancelable: true,
        detail: 2,
        view: window,
      }),
    );
  });

  const openedOnSyntheticDoubleClick = await filePreview
    .waitFor({ state: "visible", timeout: 2_000 })
    .then(() => true)
    .catch(() => false);

  if (!openedOnSyntheticDoubleClick) {
    await row.dblclick();
  }

  await expect(filePreview).toBeVisible({ timeout: 20_000 });
  await expect(
    filePreview.getByRole("heading", { name: itemName, exact: true }),
  ).toBeVisible({ timeout: 20_000 });
  return filePreview;
};

export const closeMountPreview = async (page: Page, _mountUrl: string) => {
  const filePreview = page.getByTestId("file-preview");
  const previewVisible = await filePreview.isVisible().catch(() => false);
  if (previewVisible) {
    await filePreview.getByTestId("file-preview-close").click();
    await expect(filePreview).toBeHidden({ timeout: 20_000 });
    await expect
      .poll(() => filePreview.isVisible().catch(() => false), { timeout: 5_000 })
      .toBe(false);
  }

  const resetSelectionButton = page.getByRole("button", { name: "Reset selection" });
  if (await resetSelectionButton.isVisible().catch(() => false)) {
    await resetSelectionButton.click();
    await expect(resetSelectionButton).toBeHidden({ timeout: 10_000 });
  }
};
