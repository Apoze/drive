import test, { BrowserContext, Page, expect } from "@playwright/test";
import { clearDb, dismissReleaseNotesIfPresent, login } from "./utils-common";
import fs from "fs";
import path from "path";
import { clickToMyFiles } from "./utils-navigate";
import { clickOnRowItemActions, expectRowItem } from "./utils-embedded-grid";

const forceLoopbackForMediaBase = async (page: Page) => {
  await page.route("http://localhost:8083/**", async (route) => {
    const url = route.request().url();
    await route.continue({
      url: url.replace("http://localhost:8083", "http://127.0.0.1:8083"),
    });
  });
};

const writeFile = (filepath: string, data: Buffer | string) => {
  fs.mkdirSync(path.dirname(filepath), { recursive: true });
  fs.writeFileSync(filepath, data);
  return filepath;
};

const grantClipboardPermissions = async (
  browserName: string,
  context: BrowserContext
) => {
  if (browserName === "chromium" || browserName === "webkit") {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  }
};

test("Share url leads to standalone file preview", async ({
  page,
  context,
  browserName,
}, testInfo) => {
  testInfo.setTimeout(120000);
  // On the CI the evaluateHandle is not working with webkit.
  if (browserName === "webkit") {
    return;
  }
  await grantClipboardPermissions(browserName, context);
  await context.addInitScript(() => {
    // Some E2E origins are plain HTTP (LAN dev), where `navigator.clipboard` may be undefined.
    // Provide a minimal shim so the "Copy link" UI works without crashing.
    (window as any).__e2eClipboardText = "";
    const clipboard = {
      writeText: async (text: string) => {
        (window as any).__e2eClipboardText = String(text || "");
      },
      readText: async () => String((window as any).__e2eClipboardText || ""),
    };
    try {
      Object.defineProperty(navigator, "clipboard", {
        value: clipboard,
        configurable: true,
      });
    } catch {
      // ignore
    }
  });
  await clearDb();
  await login(page, "drive@example.com");
  await forceLoopbackForMediaBase(page);
  await page.goto("/");
  await clickToMyFiles(page);
  await dismissReleaseNotesIfPresent(page);

  const stamp = `${testInfo.workerIndex}_${Date.now()}`;
  const pdfName = `pv_cm_${stamp}.pdf`;
  const pdfAsset = path.join(__dirname, "/assets/pv_cm.pdf");
  const pdfPath = writeFile(testInfo.outputPath(pdfName), fs.readFileSync(pdfAsset));

  //   Start waiting for file chooser before clicking. Note no await.
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Import" }).click();
  await page.getByRole("menuitem", { name: "Import files" }).click();

  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(pdfPath);

  await expectRowItem(page, pdfName);
  await clickOnRowItemActions(page, pdfName, "Share");
  await page.getByRole("button", { name: "link Copy link" }).click();

  await expect
    .poll(
      async () =>
        page.evaluate(() => String((window as any).__e2eClipboardText || "")),
      {
      timeout: 10000,
      }
    )
    .toContain("/explorer/items/files/");

  const clipboardContent = await page.evaluate(() =>
    String((window as any).__e2eClipboardText || "")
  );

  await page.goto(clipboardContent, { waitUntil: "domcontentloaded" });

  await expect(page).toHaveURL(/\/explorer\/items\/files\/[0-9a-f-]{36}/i);

  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible();
  await expect(filePreview.getByText(pdfName)).toBeVisible();
  // Standalone file preview should not show the Drive explorer navigation.
  await expect(page.getByRole("link", { name: "My files" })).not.toBeVisible();
  await expect(filePreview.getByTestId("file-preview-nav")).not.toBeVisible();
});

test("Wrong url leads to 404 instead of standalone file preview", async ({
  page,
}) => {
  await login(page, "drive@example.com");
  await page.goto("/explorer/items/files/not_a_uuid");

  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).not.toBeVisible();

  await page.getByText("The file you are looking for").click();
});
