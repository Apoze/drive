import test, { expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { login } from "./utils-common";
import { getRowItem, expectRowItem, expectRowItemIsNotVisible } from "./utils-embedded-grid";

test.setTimeout(2 * 60 * 1000);

test("PDF preview iframe fills the modal height", async ({ page }, testInfo) => {
  await login(page, "drive@example.com");
  await page.goto("/explorer/items/my-files");

  const releaseNotes = page
    .getByRole("dialog")
    .filter({ hasText: /updates to drive/i });
  try {
    await releaseNotes.waitFor({ state: "visible", timeout: 5000 });
    await releaseNotes.getByRole("button", { name: /^close$/i }).click();
    await expect(releaseNotes).toBeHidden();
  } catch {
    // Modal not shown for this user/session.
  }

  await expect(page.getByRole("button", { name: "Import" })).toBeVisible({
    timeout: 20000,
  });

  const sourcePdf = path.join(__dirname, "/assets/pv_cm.pdf");
  const uniqueName = `pv_cm_layout_${testInfo.workerIndex}_${Date.now()}.pdf`;
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
  await expect(filePreview).toBeVisible({ timeout: 20000 });

  const iframe = filePreview.locator("iframe.pdf-container__iframe");
  await expect(iframe).toBeVisible();
  const box = await iframe.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.height).toBeGreaterThan(300);

  await filePreview.getByRole("button", { name: "close" }).click();
  await expect(filePreview).toBeHidden({ timeout: 10000 });

  await item.click({ force: true });
  await page.getByRole("button", { name: "Delete" }).click();
  await expectRowItemIsNotVisible(page, uniqueName);
});
