import test, { expect, type Page } from "@playwright/test";
import fs from "fs";
import path from "path";
import { clearDb, dismissReleaseNotesIfPresent, login } from "./utils-common";

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

const getFirstMountId = async (page: Page) => {
  const apiOrigin = process.env.E2E_API_ORIGIN || "http://127.0.0.1:8071";
  let mountId = "";
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const response = await page.request.get(`${apiOrigin}/api/v1.0/mounts/`);
    if (response.ok()) {
      const payload = (await response.json()) as Array<{ mount_id?: string }>;
      mountId = payload[0]?.mount_id ?? "";
      break;
    }
    if (response.status() !== 401) {
      throw new Error(`mount discovery failed: ${response.status()}`);
    }
    await page.waitForTimeout(500);
  }
  expect(mountId).not.toEqual("");
  return mountId;
};

const closeFeedbackDialogIfPresent = async (page: Page) => {
  const dialog = page.getByRole("dialog", { name: "New feedback" });
  if ((await dialog.count()) === 0) return;
  const close = dialog.getByRole("button", { name: "close" });
  if (await close.isVisible().catch(() => false)) {
    await close.click();
  }
};

const openMountExplorer = async (page: Page) => {
  await page.goto("/explorer/mounts");
  await dismissReleaseNotesIfPresent(page);
  await closeFeedbackDialogIfPresent(page);
  const mountId = await getFirstMountId(page);
  const mountUrl = `/explorer/mounts/${mountId}`;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await page.goto(mountUrl, { waitUntil: "commit" }).catch(() => {
      // WebKit can report an interrupted navigation if the app triggers a concurrent
      // transition while the final mount route is already being loaded.
    });
    if (await page.getByRole("button", { name: "Login" }).first().isVisible().catch(() => false)) {
      await login(page, "drive@example.com");
      continue;
    }
    const onMountRoute = await expect
      .poll(() => /\/explorer\/mounts\/[^/?#]+/.test(page.url()), {
        timeout: 5_000,
      })
      .toBeTruthy()
      .then(() => true)
      .catch(() => false);
    if (onMountRoute) {
      break;
    }
  }
  await expect.poll(() => page.url(), { timeout: 20_000 }).toMatch(
    /\/explorer\/mounts\/[^/?#]+/,
  );
  await closeFeedbackDialogIfPresent(page);
  return mountId;
};

const uploadFilesToMount = async (page: Page, files: string[]) => {
  for (const file of files) {
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Upload" }).click();
    const chooser = await fileChooserPromise;
    await chooser.setFiles([file]);
    await expect(
      page.getByRole("button", { name: path.basename(file), exact: true }).first(),
    ).toBeVisible({ timeout: 20_000 });
  }
};

const openMountFilePreview = async (page: Page, itemName: string) => {
  const explorerTable = page
    .getByRole("table")
    .filter({ has: page.getByRole("columnheader", { name: /^Name$/i }) })
    .or(page.getByRole("table").filter({ has: page.getByRole("cell", { name: /^Name$/i }) }))
    .first();
  const escapedName = itemName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const row = explorerTable.getByRole("row", { name: new RegExp(escapedName) }).first();
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

const closePreview = async (page: Page, mountUrl: string) => {
  const filePreview = page.getByTestId("file-preview");
  await page.keyboard.press("Escape");
  const closedWithEscape = await filePreview
    .waitFor({ state: "hidden", timeout: 2_000 })
    .then(() => true)
    .catch(() => false);
  if (!closedWithEscape) {
    await filePreview.locator(".file-preview-header__content-left button").first().click();
  }
  const closedWithUi = await filePreview
    .waitFor({ state: "hidden", timeout: 8_000 })
    .then(() => true)
    .catch(() => false);
  if (!closedWithUi) {
    await page.goto(mountUrl);
    if (await page.getByRole("button", { name: "Login" }).first().isVisible().catch(() => false)) {
      await login(page, "drive@example.com");
      await page.goto(mountUrl);
    }
    await expect(filePreview).toBeHidden({ timeout: 20_000 });
  }
  const resetSelectionButton = page.getByRole("button", { name: "Reset selection" });
  if (await resetSelectionButton.isVisible().catch(() => false)) {
    await resetSelectionButton.click();
    await expect(resetSelectionButton).toBeHidden({ timeout: 10_000 });
  }
};

test("Mount previews stay stable across reopen cycles for text, WOPI, pdf and archives", async ({
  page,
  browserName,
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
  await clearDb(page);
  await login(page, "drive@example.com");

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

  const mountId = await openMountExplorer(page);
  expect(mountId).not.toEqual("");
  const mountUrl = `/explorer/mounts/${mountId}`;

  const stamp = `${testInfo.workerIndex}_${Date.now()}`;
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

  await uploadFilesToMount(page, [mdPath, txtPath, pdfPath, zipPath]);

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
    await closePreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, mdName);
    await expect(filePreview.getByText(mdMarker)).toBeVisible({ timeout: 20_000 });
    await closePreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, pdfName);
    await expect(filePreview.locator("iframe")).toBeVisible({ timeout: 20_000 });
    await closePreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, mdName);
    await expect(filePreview.getByText(mdMarker)).toBeVisible({ timeout: 20_000 });
    await closePreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, txtName);
    await expect(filePreview.locator('iframe[name="office_frame"]')).toBeVisible({
      timeout: 60_000,
    });
    await closePreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, zipName);
    await expect(filePreview.locator(".archive-viewer")).toBeVisible({ timeout: 20_000 });
    await expect(filePreview.getByText("Archive contents")).toBeVisible();
    await closePreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, mdName);
    await expect(filePreview.getByText(mdMarker)).toBeVisible({ timeout: 20_000 });
    await closePreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, zipName);
    await expect(filePreview.locator(".archive-viewer")).toBeVisible({ timeout: 20_000 });
    await closePreview(page, mountUrl);
  }

  {
    const filePreview = await openMountFilePreview(page, txtName);
    await expect(filePreview.locator('iframe[name="office_frame"]')).toBeVisible({
      timeout: 60_000,
    });
    await closePreview(page, mountUrl);
  }
});
