import test, { expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { clearDb, login } from "./utils-common";
import { clickToMyFiles } from "./utils-navigate";

const writeFile = (filepath: string, data: Buffer | string) => {
  fs.mkdirSync(path.dirname(filepath), { recursive: true });
  fs.writeFileSync(filepath, data);
  return filepath;
};

const makeZipWithEmptyFile = (innerName: string) => {
  const filename = Buffer.from(innerName, "utf8");

  const localHeader = Buffer.alloc(30);
  localHeader.writeUInt32LE(0x04034b50, 0); // local file header signature
  localHeader.writeUInt16LE(20, 4); // version needed
  localHeader.writeUInt16LE(0, 6); // flags
  localHeader.writeUInt16LE(0, 8); // compression (store)
  localHeader.writeUInt16LE(0, 10); // mod time
  localHeader.writeUInt16LE(0, 12); // mod date
  localHeader.writeUInt32LE(0, 14); // crc32
  localHeader.writeUInt32LE(0, 18); // compressed size
  localHeader.writeUInt32LE(0, 22); // uncompressed size
  localHeader.writeUInt16LE(filename.length, 26); // file name length
  localHeader.writeUInt16LE(0, 28); // extra length

  const centralDir = Buffer.alloc(46);
  centralDir.writeUInt32LE(0x02014b50, 0); // central directory signature
  centralDir.writeUInt16LE(20, 4); // version made by
  centralDir.writeUInt16LE(20, 6); // version needed
  centralDir.writeUInt16LE(0, 8); // flags
  centralDir.writeUInt16LE(0, 10); // compression
  centralDir.writeUInt16LE(0, 12); // mod time
  centralDir.writeUInt16LE(0, 14); // mod date
  centralDir.writeUInt32LE(0, 16); // crc32
  centralDir.writeUInt32LE(0, 20); // compressed size
  centralDir.writeUInt32LE(0, 24); // uncompressed size
  centralDir.writeUInt16LE(filename.length, 28); // file name length
  centralDir.writeUInt16LE(0, 30); // extra length
  centralDir.writeUInt16LE(0, 32); // comment length
  centralDir.writeUInt16LE(0, 34); // disk start
  centralDir.writeUInt16LE(0, 36); // internal attrs
  centralDir.writeUInt32LE(0, 38); // external attrs
  centralDir.writeUInt32LE(0, 42); // local header offset

  const centralDirOffset = localHeader.length + filename.length;
  const centralDirSize = centralDir.length + filename.length;

  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0); // EOCD signature
  eocd.writeUInt16LE(0, 4); // disk number
  eocd.writeUInt16LE(0, 6); // disk with central directory
  eocd.writeUInt16LE(1, 8); // entries on this disk
  eocd.writeUInt16LE(1, 10); // total entries
  eocd.writeUInt32LE(centralDirSize, 12); // central dir size
  eocd.writeUInt32LE(centralDirOffset, 16); // central dir offset
  eocd.writeUInt16LE(0, 20); // comment length

  return Buffer.concat([localHeader, filename, centralDir, filename, eocd]);
};

test("Viewer routing: .inf => text, .sys => preview unavailable, .zip => archive", async ({
  page,
}, testInfo) => {
  testInfo.setTimeout(120000);
  await clearDb();
  await login(page, "drive@example.com");
  await page.goto("/");
  await clickToMyFiles(page);

  const explorerTable = page
    .getByRole("table")
    .filter({ has: page.getByRole("columnheader", { name: /^Name$/i }) })
    .or(page.getByRole("table").filter({ has: page.getByRole("cell", { name: /^Name$/i }) }))
    .first();

  const openFromGrid = async (itemName: string) => {
    const target = explorerTable.getByRole("button", { name: itemName, exact: true }).last();
    await expect(target).toBeVisible({ timeout: 20_000 });
    // The explorer grid is wrapped by dnd-kit and can set aria-disabled on interactive children;
    // force the action so Playwright still dispatches the double click.
    await target.dblclick({ force: true });
  };

  const stamp = `${testInfo.workerIndex}_${Date.now()}`;
  const infName = `viewer_route_inf_${stamp}.inf`;
  const infUtf16Name = `viewer_route_inf_utf16_${stamp}.inf`;
  const sysName = `viewer_route_sys_${stamp}.sys`;
  const zipName = `viewer_route_zip_${stamp}.zip`;

  const infPath = writeFile(
    testInfo.outputPath(infName),
    "[Version]\nSignature=\"$Windows NT$\"\n",
  );
  const infUtf16Path = writeFile(
    testInfo.outputPath(infUtf16Name),
    Buffer.concat([
      Buffer.from([0xff, 0xfe]),
      Buffer.from("[Version]\r\nSignature=\"$Windows NT$\"\r\n", "utf16le"),
    ]),
  );
  const sysPath = writeFile(
    testInfo.outputPath(sysName),
    Buffer.from([0x7f, 0x45, 0x4c, 0x46, 0x00, 0x02, 0x01, 0x01, 0x00]),
  );
  const zipPath = writeFile(testInfo.outputPath(zipName), makeZipWithEmptyFile("empty.txt"));

  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Import" }).click();
  await page.getByRole("menuitem", { name: "Import files" }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles([infPath, infUtf16Path, sysPath, zipPath]);

  await expect(page.getByText("Drop your files here")).not.toBeVisible();

  // .inf => CodeMirror text viewer
  await openFromGrid(infName);
  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible({ timeout: 20000 });
  await expect(filePreview.getByText("Signature")).toBeVisible({ timeout: 20000 });
  await filePreview.getByRole("button", { name: "close" }).click();
  await expect(filePreview).toBeHidden({ timeout: 10000 });

  // UTF-16 .inf => CodeMirror text viewer (read-only) with edit disabled + warning
  await openFromGrid(infUtf16Name);
  await expect(filePreview).toBeVisible({ timeout: 20000 });
  const roInfo = filePreview.getByTestId("text-readonly-info");
  await expect(roInfo).toBeVisible({ timeout: 20000 });
  await expect(filePreview.getByText("Signature")).toBeVisible({ timeout: 20000 });
  const editButton = filePreview.getByRole("button", { name: "Edit" });
  await expect(editButton).toBeVisible({ timeout: 20000 });
  await expect(editButton).toBeDisabled();
  await roInfo.click();
  await expect(page.locator(".Toastify__toast--info").getByText(/utf-16le/i)).toBeVisible();
  await filePreview.getByRole("button", { name: "close" }).click();
  await expect(filePreview).toBeHidden({ timeout: 10000 });

  // .sys => Preview unavailable (and NOT archive)
  await openFromGrid(sysName);
  await expect(filePreview).toBeVisible({ timeout: 20000 });
  await expect(filePreview.locator(".file-preview-unsupported")).toBeVisible();
  await expect(filePreview.getByText("Preview not available")).toBeVisible();
  await expect(filePreview.locator(".archive-viewer")).not.toBeVisible();
  await expect(filePreview.locator(".text-preview")).not.toBeVisible();
  await filePreview.getByRole("button", { name: "close" }).click();
  await expect(filePreview).toBeHidden({ timeout: 10000 });

  // .zip => Archive viewer
  await openFromGrid(zipName);
  await expect(filePreview).toBeVisible({ timeout: 20000 });
  await expect(filePreview.locator(".archive-viewer")).toBeVisible({ timeout: 20000 });
  await expect(filePreview.getByText("Archive contents")).toBeVisible();
  await expect(filePreview.locator(".file-preview-unsupported")).not.toBeVisible();
});
