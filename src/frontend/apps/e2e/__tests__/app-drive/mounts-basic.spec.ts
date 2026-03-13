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

const getFirstMountId = async (page: import("@playwright/test").Page) => {
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

const getExplorerTable = (page: import("@playwright/test").Page) =>
  page
    .getByRole("table")
    .filter({ has: page.getByRole("columnheader", { name: /^Name$/i }) })
    .or(page.getByRole("table").filter({ has: page.getByRole("cell", { name: /^Name$/i }) }))
    .first();

const getMountRow = (
  page: import("@playwright/test").Page,
  itemName: string,
) => {
  const escapedName = itemName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return getExplorerTable(page)
    .getByRole("row", { name: new RegExp(escapedName) })
    .first();
};

test("Mounts (MountProvider/SMB): upload, preview (streaming), download, WOPI init", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.E2E_ENABLE_MOUNTS !== "1",
    "Mounts E2E is disabled by default",
  );
  testInfo.setTimeout(180000);
  await clearDb(page);
  await login(page, "drive@example.com");

  const closeFeedbackDialogIfPresent = async () => {
    const dialog = page.getByRole("dialog", { name: "New feedback" });
    if ((await dialog.count()) === 0) return;
    const close = dialog.getByRole("button", { name: "close" });
    if (await close.isVisible().catch(() => false)) {
      await close.click();
    }
  };

  await page.goto("/explorer/mounts");
  await dismissReleaseNotesIfPresent(page);
  await closeFeedbackDialogIfPresent();
  const mountId = await getFirstMountId(page);
  expect(mountId).not.toEqual("");
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
  await expect(getMountRow(page, pdfName)).toBeVisible({
    timeout: 20000,
  });

  // Upload an office file for WOPI (DOCX).
  {
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Upload" }).click();
    const chooser = await fileChooserPromise;
    await chooser.setFiles([docxPath]);
  }
  await expect(getMountRow(page, docxName)).toBeVisible({
    timeout: 20000,
  });

  // Select the PDF entry, then preview it.
  await getMountRow(page, pdfName).click();
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
  expect(src).toContain(`/api/v1.0/mount-stream/`);

  // Navigate back to the mount folder, then validate the download action opens the backend URL.
  await page.goto(`/explorer/mounts/${mountId}`);
  await closeFeedbackDialogIfPresent();
  await getMountRow(page, pdfName).click();
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
  await getMountRow(page, docxName).click();
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
