import test, { expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { clearDb, dismissReleaseNotesIfPresent, login } from "./utils-common";

const DOCX_BASE64 =
  "UEsDBBQAAAAIAABcUVydxYoq8gAAALkBAAATAAAAW0NvbnRlbnRfVHlwZXNdLnhtbH2QzU7DMBCE73kKy1eUOHBACCXpgZ8jcCgPsLI3iVV7bXnd0r49TgtFQpSjNfPNrKdb7b0TO0xsA/XyummlQNLBWJp6+b5+ru+k4AxkwAXCXh6Q5WqouvUhIosCE/dyzjneK8V6Rg/chIhUlDEkD7k806Qi6A1MqG7a9lbpQBkp13nJkEMlRPeII2xdFk/7opxuSehYioeTd6nrJcTorIZcdLUj86uo/ippCnn08GwjXxWDVJdKFvFyxw/6WiZK1qB4g5RfwBej+gjJKBP01he4+T/pj2vDOFqNZ35JiyloZC7be9ecFQ+Wvn/RqePwQ/UJUEsDBBQAAAAIAABcUVxAoFMJsgAAAC8BAAALAAAAX3JlbHMvLnJlbHONz7sOgjAUBuCdp2jOLgUHYwyFxZiwGnyApj2URnpJWy+8vR0cxDg4ntt38jfd08zkjiFqZxnUZQUErXBSW8XgMpw2eyAxcSv57CwyWDBC1xbNGWee8k2ctI8kIzYymFLyB0qjmNDwWDqPNk9GFwxPuQyKei6uXCHdVtWOhk8D2oKQFUt6ySD0sgYyLB7/4d04aoFHJ24Gbfrx5WsjyzwoTAweLkgq3+0ys0BzSrqK2RYvUEsDBBQAAAAIAABcUVyw8MvNqgAAAOwAAAARAAAAd29yZC9kb2N1bWVudC54bWw9jjEOwjAMRfeeIsoOKQwIVW26IUYGOEBIDFRK7CgOFG5PUgmWp/9l69n9+A5evCDxRDjIzbqVAtCSm/A+yMv5sNpLwdmgM54QBvkBlqNu+rlzZJ8BMItiQO7mQT5yjp1SbB8QDK8pApbZjVIwudR0VzMlFxNZYC4Hglfbtt2pYCaUuhGiWK/kPjUuJeqCVJH1EbynXtVYmRbG/yqDzaekFov6aWr6vambL1BLAQIUAxQAAAAIAABcUVydxYoq8gAAALkBAAATAAAAAAAAAAAAAACAAQAAAABbQ29udGVudF9UeXBlc10ueG1sUEsBAhQDFAAAAAgAAFxRXECgUwmyAAAALwEAAAsAAAAAAAAAAAAAAIABIwEAAF9yZWxzLy5yZWxzUEsBAhQDFAAAAAgAAFxRXLDwy82qAAAA7AAAABEAAAAAAAAAAAAAAIAB/gEAAHdvcmQvZG9jdW1lbnQueG1sUEsFBgAAAAADAAMAuQAAANcCAAAAAA==";

const writeFile = (filepath: string, data: Buffer | string) => {
  fs.mkdirSync(path.dirname(filepath), { recursive: true });
  fs.writeFileSync(filepath, data);
  return filepath;
};

const getMountIdFromUrl = (url: string) => {
  const { pathname } = new URL(url);
  const parts = pathname.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? "";
};

test("Mounts (MountProvider/SMB): upload, preview (streaming), download, WOPI init", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.E2E_ENABLE_MOUNTS !== "1",
    "Mounts E2E is disabled by default",
  );
  testInfo.setTimeout(180000);
  await clearDb();
  await login(page, "drive@example.com");

  const closeFeedbackDialogIfPresent = async () => {
    const dialog = page.getByRole("dialog", { name: "New feedback" });
    if ((await dialog.count()) === 0) return;
    const close = dialog.getByRole("button", { name: "close" });
    if (await close.isVisible().catch(() => false)) {
      await close.click();
    }
  };

  await page.goto("/");
  await dismissReleaseNotesIfPresent(page);
  await page.getByRole("link", { name: "Mounts" }).click({ noWaitAfter: true });
  await expect(page.getByRole("heading", { name: "Mounts" })).toBeVisible();
  await closeFeedbackDialogIfPresent();

  await page.getByRole("link", { name: "Browse", exact: true }).first().click();
  await page.waitForURL(/\/explorer\/mounts\/[^/?#]+/);
  const mountId = getMountIdFromUrl(page.url());
  expect(mountId).not.toEqual("");
  await closeFeedbackDialogIfPresent();

  const stamp = `${testInfo.workerIndex}_${Date.now()}`;
  const pdfName = `mount_preview_${stamp}.pdf`;
  const docxName = `mount_wopi_${stamp}.docx`;

  const pdfAsset = path.join(__dirname, "assets", "pv_cm.pdf");
  const pdfPath = writeFile(testInfo.outputPath(pdfName), fs.readFileSync(pdfAsset));
  const docxPath = writeFile(
    testInfo.outputPath(docxName),
    Buffer.from(DOCX_BASE64, "base64"),
  );

  // Upload a previewable file (PDF).
  await expect(page.getByRole("button", { name: "Upload" })).toBeEnabled();
  {
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Upload" }).click();
    const chooser = await fileChooserPromise;
    await chooser.setFiles([pdfPath]);
  }
  await expect(page.getByRole("button", { name: pdfName })).toBeVisible({
    timeout: 20000,
  });

  // Upload an office file for WOPI (DOCX).
  {
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Upload" }).click();
    const chooser = await fileChooserPromise;
    await chooser.setFiles([docxPath]);
  }
  await expect(page.getByRole("button", { name: docxName })).toBeVisible({
    timeout: 20000,
  });

  // Select the PDF entry, then preview it.
  await page.getByRole("button", { name: pdfName }).click();
  const previewButton = page
    .getByRole("button", { name: "Preview", exact: true })
    .first();
  await expect(previewButton).toBeEnabled();
  await previewButton.click();

  const iframe = page.locator("iframe");
  await expect(iframe).toBeVisible({ timeout: 20000 });
  const src = await iframe.getAttribute("src");
  expect(src).toBeTruthy();
  expect(src).not.toMatch(/^blob:/);
  expect(src).toContain(`/api/v1.0/mounts/${mountId}/preview/`);

  // Navigate back to the mount folder, then validate the download action opens the backend URL.
  await page.goto(`/explorer/mounts/${mountId}`);
  await closeFeedbackDialogIfPresent();
  await page.getByRole("button", { name: pdfName }).click();
  const downloadButton = page.getByRole("button", {
    name: "Download",
    exact: true,
  });
  await expect(downloadButton).toBeEnabled();
  const popupPromise = page.waitForEvent("popup");
  await downloadButton.click();
  const popup = await popupPromise;
  await popup.close();

  // Validate the download endpoint is reachable (streaming) for the current user.
  const apiOrigin = process.env.E2E_API_ORIGIN || "http://192.168.10.123:8071";
  const downloadQuery = new URLSearchParams({ path: `/${pdfName}` });
  const downloadRes = await page.request.get(
    `${apiOrigin}/api/v1.0/mounts/${mountId}/download/?${downloadQuery.toString()}`,
  );
  expect(downloadRes.ok()).toBeTruthy();

  // Stub external editor load; we only need to ensure init works and the UI attempts to open.
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

  // Select the DOCX entry, then start WOPI.
  await page.goto(`/explorer/mounts/${mountId}`);
  await closeFeedbackDialogIfPresent();
  await page.getByRole("button", { name: docxName }).click();
  const onlineEditingButton = page.getByRole("button", {
    name: "Online editing",
    exact: true,
  });
  await expect(onlineEditingButton).toBeEnabled();

  const initResponsePromise = page.waitForResponse((resp) => {
    return (
      resp.url().includes(`/api/v1.0/mounts/${mountId}/wopi/`) && resp.status() === 200
    );
  });
  await onlineEditingButton.click();
  await initResponsePromise;
  await expect(page.locator('iframe[name="office_frame"]')).toBeVisible({
    timeout: 20000,
  });
});
