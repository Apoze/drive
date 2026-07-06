import { expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { test } from "./fixtures/scenarios";
import {
  closeMountPreview,
  expectMountPdfPreview,
  openMountFilePreview,
  openMountFixtureRoot,
  uploadFilesToCurrentMountFolder,
} from "./utils-mounts";

const writeFile = (filepath: string, data: Buffer | string) => {
  fs.mkdirSync(path.dirname(filepath), { recursive: true });
  fs.writeFileSync(filepath, data);
  return filepath;
};

const makeZipWithEmptyFile = (innerName: string) => {
  const filename = Buffer.from(innerName, "utf8");

  const localHeader = Buffer.alloc(30);
  localHeader.writeUInt32LE(0x04034b50, 0);
  localHeader.writeUInt16LE(20, 4);
  localHeader.writeUInt16LE(0, 6);
  localHeader.writeUInt16LE(0, 8);
  localHeader.writeUInt16LE(0, 10);
  localHeader.writeUInt16LE(0, 12);
  localHeader.writeUInt32LE(0, 14);
  localHeader.writeUInt32LE(0, 18);
  localHeader.writeUInt32LE(0, 22);
  localHeader.writeUInt16LE(filename.length, 26);
  localHeader.writeUInt16LE(0, 28);

  const centralDir = Buffer.alloc(46);
  centralDir.writeUInt32LE(0x02014b50, 0);
  centralDir.writeUInt16LE(20, 4);
  centralDir.writeUInt16LE(20, 6);
  centralDir.writeUInt16LE(0, 8);
  centralDir.writeUInt16LE(0, 10);
  centralDir.writeUInt16LE(0, 12);
  centralDir.writeUInt16LE(0, 14);
  centralDir.writeUInt32LE(0, 16);
  centralDir.writeUInt32LE(0, 20);
  centralDir.writeUInt32LE(0, 24);
  centralDir.writeUInt16LE(filename.length, 28);
  centralDir.writeUInt16LE(0, 30);
  centralDir.writeUInt16LE(0, 32);
  centralDir.writeUInt16LE(0, 34);
  centralDir.writeUInt16LE(0, 36);
  centralDir.writeUInt32LE(0, 38);
  centralDir.writeUInt32LE(0, 42);

  const centralDirOffset = localHeader.length + filename.length;
  const centralDirSize = centralDir.length + filename.length;

  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(1, 8);
  eocd.writeUInt16LE(1, 10);
  eocd.writeUInt32LE(centralDirSize, 12);
  eocd.writeUInt32LE(centralDirOffset, 16);
  eocd.writeUInt16LE(0, 20);

  return Buffer.concat([localHeader, filename, centralDir, filename, eocd]);
};

test("Mount previews stay stable across reopen cycles for text, WOPI, pdf and archives", async ({
  page,
  browserName,
  mountFixtureTree,
  primaryActor,
}, testInfo) => {
  test.skip(
    process.env.E2E_ENABLE_MOUNTS !== "1",
    "Mounts E2E is disabled by default",
  );
  test.skip(
    browserName !== "chromium",
    "The full mount preview cycle regression is asserted in Chromium; WebKit and Firefox keep the basic mount preview coverage.",
  );
  testInfo.setTimeout(240000);

  await page.route(/:9980\//, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<html><body>stubbed editor</body></html>",
    });
  });
  await page.route(/:9981\//, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<html><body>stubbed editor</body></html>",
    });
  });

  const mountUrl = await openMountFixtureRoot({
    page,
    primaryActor,
    mountFixtureTree,
  });

  const stamp = mountFixtureTree.scope.scenario_slug;
  const mdName = `mount_notes_${stamp}.md`;
  const txtName = `mount_notes_${stamp}.txt`;
  const pdfName = `mount_preview_${stamp}.pdf`;
  const zipName = `mount_bundle_${stamp}.zip`;

  const mdPath = writeFile(
    testInfo.outputPath(mdName),
    "# Mount preview regression\n\ninitial text\n",
  );
  const txtPath = writeFile(
    testInfo.outputPath(txtName),
    "plain text through wopi\n",
  );
  const pdfAsset = path.join(__dirname, "assets", "pv_cm.pdf");
  const pdfPath = writeFile(testInfo.outputPath(pdfName), fs.readFileSync(pdfAsset));
  const zipPath = writeFile(
    testInfo.outputPath(zipName),
    makeZipWithEmptyFile("notes.txt"),
  );

  await uploadFilesToCurrentMountFolder(page, [mdPath, txtPath, pdfPath, zipPath]);

  const mdMarker = `mount-cycle-marker-${stamp}`;

  {
    const filePreview = await openMountFilePreview(page, mdName);
    await expect(filePreview.getByText("Mount preview regression")).toBeVisible({
      timeout: 20_000,
    });
    const editButton = filePreview.getByRole("button", { name: "Edit" });
    await expect(editButton).toBeEnabled();
    await editButton.click();
    await filePreview.locator(".cm-content").click();
    await page.keyboard.press("End");
    await page.keyboard.type(`\n${mdMarker}`);
    await filePreview.getByRole("button", { name: "Save" }).click();
    await expect(page.locator(".Toastify__toast--success").getByText("Saved.")).toBeVisible({
      timeout: 20_000,
    });
    await closeMountPreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, mdName);
    await expect(filePreview.getByText(mdMarker)).toBeVisible({ timeout: 20_000 });
    await closeMountPreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, pdfName);
    await expectMountPdfPreview(filePreview);
    await closeMountPreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, mdName);
    await expect(filePreview.getByText(mdMarker)).toBeVisible({ timeout: 20_000 });
    await closeMountPreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, txtName);
    await expect(filePreview.locator('iframe[name="office_frame"]')).toBeVisible({
      timeout: 60_000,
    });
    await closeMountPreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, zipName);
    await expect(filePreview.locator(".archive-viewer")).toBeVisible({ timeout: 20_000 });
    await expect(filePreview.getByText("Archive contents")).toBeVisible();
    await closeMountPreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, mdName);
    await expect(filePreview.getByText(mdMarker)).toBeVisible({ timeout: 20_000 });
    await closeMountPreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, zipName);
    await expect(filePreview.locator(".archive-viewer")).toBeVisible({ timeout: 20_000 });
    await closeMountPreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, txtName);
    await expect(filePreview.locator('iframe[name="office_frame"]')).toBeVisible({
      timeout: 60_000,
    });
    await closeMountPreview(page, mountUrl);
  }
});
