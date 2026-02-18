import test, { expect } from "@playwright/test";
import { clearDb, login } from "./utils-common";
import fs from "fs";
import path from "path";
import { clickToMyFiles } from "./utils-navigate";

const writeFile = (filepath: string, data: Buffer | string) => {
  fs.mkdirSync(path.dirname(filepath), { recursive: true });
  fs.writeFileSync(filepath, data);
  return filepath;
};

test("Display HEIC not supported message when opening a HEIC file", async ({
  page,
}, testInfo) => {
  await clearDb();
  await login(page, "drive@example.com");
  await page.goto("/");
  await clickToMyFiles(page);

  // Use the real HEIC file from assets
  const stamp = `${testInfo.workerIndex}_${Date.now()}`;
  const heicName = `test-image-${stamp}.heic`;
  const heicAsset = path.join(__dirname, "/assets/test-image.heic");
  const heicFilePath = writeFile(
    testInfo.outputPath(heicName),
    fs.readFileSync(heicAsset),
  );

  // Upload the HEIC file
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Import" }).click();
  await page.getByRole("menuitem", { name: "Import files" }).click();

  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(heicFilePath);

  // Wait for the file to be uploaded and visible in the list
  await expect(page.getByText("Drop your files here")).not.toBeVisible();
  const heicCell = page.getByRole("cell", { name: heicName, exact: true });
  await expect(heicCell).toBeVisible(
    {
      timeout: 10000,
    }
  );

  // Click on the HEIC file to open the preview
  await heicCell.dblclick();

  // Check that the file preview is visible
  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible();

  // Check that the HEIC-specific message is displayed
  await expect(
    filePreview.getByText("HEIC files are not yet supported for preview.")
  ).toBeVisible();
});
