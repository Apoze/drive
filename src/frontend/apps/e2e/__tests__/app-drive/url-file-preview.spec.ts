import { Page, expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { test } from "./fixtures/scenarios";
import { dismissReleaseNotesIfPresent } from "./utils-common";
import { openFolderFromMainWorkspace } from "./utils-navigate";
import { clickOnRowItemActions, expectRowItem } from "./utils-embedded-grid";
import { uploadFile } from "./utils/upload-utils";
import {
  createAnonymousBrowserContext,
  forceAnonymousFrontendConfig,
  grantClipboardPermissions,
  installClipboardShim,
} from "./utils/various-utils";
import { clickCopyLinkButton, selectLinkReach } from "./utils/share-utils";

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

const uploadFileAndCopyPublicLink = async (
  page: Page,
  pdfName: string,
  testInfo: { outputPath: (pathSegment: string) => string },
) => {
  const pdfAsset = path.join(__dirname, "/assets/pv_cm.pdf");
  const pdfPath = writeFile(
    testInfo.outputPath(pdfName),
    fs.readFileSync(pdfAsset),
  );
  await uploadFile(page, pdfPath);

  // Upload can be slower on Firefox; wait a bit longer for the row to appear.
  await expectRowItem(page, pdfName, { timeoutMs: 60_000 });
  await clickOnRowItemActions(page, pdfName, "Share");
  await selectLinkReach(page, "Public");
  await clickCopyLinkButton(page);

  await expect
    .poll(
      async () =>
        page.evaluate(() => String((window as any).__e2eClipboardText || "")),
      {
        timeout: 10000,
      },
    )
    .toContain("/explorer/items/files/");

  return page.evaluate(() => String((window as any).__e2eClipboardText || ""));
};

test("Share url leads to standalone file preview", async ({
  page,
  context,
  browserName,
  isolatedWorkspace,
}, testInfo) => {
  testInfo.setTimeout(120000);
  // On the CI the evaluateHandle is not working with webkit.
  if (browserName === "webkit") {
    return;
  }
  await grantClipboardPermissions(browserName, context);
  await installClipboardShim(context);
  await forceLoopbackForMediaBase(page);
  await page.goto("/");
  await openFolderFromMainWorkspace(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );
  await dismissReleaseNotesIfPresent(page);

  const pdfName = `pv_cm_${isolatedWorkspace.scope.scenario_slug}.pdf`;
  const clipboardContent = await uploadFileAndCopyPublicLink(
    page,
    pdfName,
    testInfo,
  );

  await page.goto(clipboardContent, { waitUntil: "domcontentloaded" });

  await expect(page).toHaveURL(/\/explorer\/items\/files\/[0-9a-f-]{36}/i);

  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible();
  await expect(filePreview.getByText(pdfName)).toBeVisible();
  // Standalone file preview should not show the Drive explorer navigation.
  await expect(page.locator(".drive__home__left-panel")).not.toBeVisible();
  await expect(filePreview.getByTestId("file-preview-nav")).not.toBeVisible();
});

test("Wrong url leads to 404 instead of standalone file preview", async ({
  page,
}) => {
  await page.goto("/explorer/items/files/not_a_uuid");

  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).not.toBeVisible();

  await page.getByText("The file you are looking for").click();
});

test("Public file preview shows My Files CTA for authenticated users", async ({
  page,
  context,
  browserName,
  isolatedWorkspace,
}, testInfo) => {
  testInfo.setTimeout(120000);
  if (browserName === "webkit") {
    return;
  }
  await grantClipboardPermissions(browserName, context);
  await installClipboardShim(context);
  await forceLoopbackForMediaBase(page);
  await page.goto("/");
  await openFolderFromMainWorkspace(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );
  await dismissReleaseNotesIfPresent(page);

  const fileUrl = await uploadFileAndCopyPublicLink(
    page,
    `public_cta_${isolatedWorkspace.scope.scenario_slug}.pdf`,
    testInfo,
  );

  await page.goto(fileUrl, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("file-preview")).toBeVisible();
  await expect(page.getByTestId("my-files-cta")).toBeVisible();
  await expect(page.getByTestId("anonymous-cta-login")).not.toBeVisible();
  await expect(page.getByTestId("anonymous-cta-try-out")).not.toBeVisible();

  await page.getByTestId("my-files-cta").click();
  await page.waitForURL("**/explorer/items/my-files");
  expect(new URL(page.url()).pathname).toBe("/explorer/items/my-files");
});

test("Public file preview shows AnonymousCTA for anonymous users", async ({
  page,
  context,
  browser,
  browserName,
  isolatedWorkspace,
}, testInfo) => {
  testInfo.setTimeout(120000);
  if (browserName === "webkit") {
    return;
  }
  await grantClipboardPermissions(browserName, context);
  await installClipboardShim(context);
  await forceLoopbackForMediaBase(page);
  await page.goto("/");
  await openFolderFromMainWorkspace(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );
  await dismissReleaseNotesIfPresent(page);

  const fileUrl = await uploadFileAndCopyPublicLink(
    page,
    `anonymous_cta_${isolatedWorkspace.scope.scenario_slug}.pdf`,
    testInfo,
  );

  const anonContext = await createAnonymousBrowserContext(browser);
  await installClipboardShim(anonContext);
  const anonPage = await anonContext.newPage();
  await forceLoopbackForMediaBase(anonPage);
  await forceAnonymousFrontendConfig(anonPage);
  await anonPage.goto(fileUrl, { waitUntil: "domcontentloaded" });

  await expect(anonPage.getByTestId("file-preview")).toBeVisible();
  await expect(anonPage.getByTestId("anonymous-cta-login")).toBeVisible();
  await expect(anonPage.getByTestId("anonymous-cta-try-out")).toBeVisible();
  await expect(anonPage.getByTestId("my-files-cta")).not.toBeVisible();
  await expect(anonPage.getByTestId("anonymous-cta-try-out")).toHaveAttribute(
    "href",
    "/",
  );

  await anonPage.getByTestId("anonymous-cta-try-out").click();
  await anonPage.waitForURL((url) => url.pathname === "/");

  await anonPage.goto(fileUrl, { waitUntil: "domcontentloaded" });
  await expect(anonPage.getByTestId("anonymous-cta-login")).toBeVisible();
  await Promise.all([
    anonPage.waitForRequest((request) =>
      request.url().includes("/authenticate/"),
    ),
    anonPage.getByTestId("anonymous-cta-login").click(),
  ]);

  await anonContext.close();
});

test("Public file preview uses FRONTEND_EXTERNAL_HOME_URL for anonymous try-out", async ({
  page,
  context,
  browser,
  browserName,
  isolatedWorkspace,
}, testInfo) => {
  testInfo.setTimeout(120000);
  if (browserName === "webkit") {
    return;
  }
  await grantClipboardPermissions(browserName, context);
  await installClipboardShim(context);
  await forceLoopbackForMediaBase(page);
  await page.goto("/");
  await openFolderFromMainWorkspace(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );
  await dismissReleaseNotesIfPresent(page);

  const fileUrl = await uploadFileAndCopyPublicLink(
    page,
    `external_home_cta_${isolatedWorkspace.scope.scenario_slug}.pdf`,
    testInfo,
  );

  const tryOutUrl = "https://try-out.example.test/";
  const anonContext = await createAnonymousBrowserContext(browser);
  await installClipboardShim(anonContext);
  const anonPage = await anonContext.newPage();
  await forceLoopbackForMediaBase(anonPage);
  await forceAnonymousFrontendConfig(anonPage, {
    FRONTEND_EXTERNAL_HOME_URL: tryOutUrl,
  });
  await anonPage.goto(fileUrl, { waitUntil: "domcontentloaded" });

  await expect(anonPage.getByTestId("file-preview")).toBeVisible();
  await expect(anonPage.getByTestId("anonymous-cta-try-out")).toHaveAttribute(
    "href",
    tryOutUrl,
  );
  await expect(anonPage.getByTestId("anonymous-cta-login")).toBeVisible();
  await expect(anonPage.getByTestId("my-files-cta")).not.toBeVisible();

  await anonContext.close();
});
