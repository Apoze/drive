import { expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { test } from "./fixtures/scenarios";
import { openFolderFromMainWorkspace } from "./utils-navigate";
import { expectRowItem, getRowItem } from "./utils-embedded-grid";
import { uploadFile } from "./utils/upload-utils";

const writeFile = (filepath: string, data: Buffer | string) => {
  fs.mkdirSync(path.dirname(filepath), { recursive: true });
  fs.writeFileSync(filepath, data);
  return filepath;
};

test("Display HEIC not supported message when opening a HEIC file", async ({
  page,
  isolatedWorkspace,
}, testInfo) => {
  await page.goto("/");
  await openFolderFromMainWorkspace(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );

  // Use the real HEIC file from assets
  const heicName = `test-image-${isolatedWorkspace.scope.scenario_slug}.heic`;
  const heicAsset = path.join(__dirname, "/assets/test-image.heic");
  const heicFilePath = writeFile(
    testInfo.outputPath(heicName),
    fs.readFileSync(heicAsset),
  );

  // Upload the HEIC file
  await uploadFile(page, heicFilePath);

  // Wait for the file to be uploaded and visible in the list
  await expect(page.getByText("Drop your files here")).not.toBeVisible();
  await expectRowItem(page, heicName, { timeoutMs: 30_000 });
  const heicCell = await getRowItem(page, heicName);

  // Click on the HEIC file to open the preview
  await heicCell.dblclick();

  // Check that the file preview is visible
  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible();

  // Check that the HEIC-specific message is displayed
  await expect(
    filePreview.getByText("HEIC files are not yet supported for preview."),
  ).toBeVisible();
});
