import { expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { test } from "./fixtures/scenarios";
import { dismissReleaseNotesIfPresent } from "./utils-common";
import { getRowItem, expectRowItem } from "./utils-embedded-grid";
import { openFolderFromMainWorkspace } from "./utils-navigate";

test.setTimeout(2 * 60 * 1000);

test("PDF preview iframe fills the modal height", async ({
  page,
  isolatedWorkspace,
}, testInfo) => {
  await page.goto("/");
  await openFolderFromMainWorkspace(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );
  await dismissReleaseNotesIfPresent(page, 5_000);

  await expect(page.getByRole("button", { name: "Import" })).toBeVisible({
    timeout: 20_000,
  });

  const sourcePdf = path.join(__dirname, "/assets/pv_cm.pdf");
  const uniqueName = `pv_cm_layout_${isolatedWorkspace.scope.scenario_slug}.pdf`;
  const tmpPdf = testInfo.outputPath(uniqueName);
  fs.copyFileSync(sourcePdf, tmpPdf);

  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Import" }).click();
  await page.getByRole("menuitem", { name: "Import files" }).click();

  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(tmpPdf);

  await expectRowItem(page, uniqueName);

  const item = await getRowItem(page, uniqueName);
  await item.dblclick();
  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible({ timeout: 20_000 });

  const iframe = filePreview.locator("iframe.pdf-container__iframe");
  await expect(iframe).toBeVisible();
  const box = await iframe.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.height).toBeGreaterThan(300);

  await filePreview.getByRole("button", { name: "close" }).click();
  await expect(filePreview).toBeHidden({ timeout: 10_000 });
});
