import { Page, expect } from "@playwright/test";
import { test } from "./fixtures/scenarios";
import { openFolderFromMainWorkspace } from "./utils-navigate";
import {
  clickCopyLinkButton,
  closeShareModal,
  openShareModal,
  selectLinkReach,
} from "./utils/share-utils";
import {
  createAnonymousBrowserContext,
  forceAnonymousFrontendConfig,
  grantClipboardPermissions,
  installClipboardShim,
} from "./utils/various-utils";
import { dismissReleaseNotesIfPresent } from "./utils-common";

const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const makeScenarioFolderPublic = async (
  page: Parameters<typeof openFolderFromMainWorkspace>[0],
  context: Parameters<typeof installClipboardShim>[0],
  folderName: string,
) => {
  await installClipboardShim(context);
  await page.goto("/");
  await openFolderFromMainWorkspace(page, folderName);
  await dismissReleaseNotesIfPresent(page);
  await openShareModal(page);
  await selectLinkReach(page, "Public");
  await expect
    .poll(
      async () => {
        await clickCopyLinkButton(page);
        return page.evaluate(() =>
          String((window as any).__e2eClipboardText || ""),
        );
      },
      { timeout: 10_000 },
    )
    .toContain("/share/");
  const shareUrl = await page.evaluate(() =>
    String((window as any).__e2eClipboardText || ""),
  );
  await closeShareModal(page);
  return shareUrl;
};

test.describe.configure({ timeout: 60_000 });

const openAnonymousPublicFolder = async (
  page: Page,
  folderUrl: string,
  folderName: string,
) => {
  await expect
    .poll(
      async () => {
        await page.goto(folderUrl, { waitUntil: "domcontentloaded" });
        await page.waitForLoadState("networkidle").catch(() => undefined);

        const isOnPublicFolder = !page.url().includes("/401");
        const hasAnonymousLogin = await page
          .getByTestId("anonymous-cta-login")
          .isVisible()
          .catch(() => false);
        const hasFolderHeading = await page
          .getByRole("heading", { name: folderName })
          .isVisible()
          .catch(() => false);

        return isOnPublicFolder && hasAnonymousLogin && hasFolderHeading;
      },
      {
        intervals: [500, 1_000, 2_000],
        timeout: 30_000,
      },
    )
    .toBe(true);

  await expect(page.getByTestId("anonymous-cta-login")).toBeVisible();
  await expect(page.getByTestId("anonymous-cta-try-out")).toBeVisible();
  await expect(page.getByRole("heading", { name: folderName })).toBeVisible();

  return page.url();
};

const openPublicFolderAsAuthenticated = async (
  page: Page,
  folderUrl: string,
  folderName: string,
) => {
  const folderNamePattern = new RegExp(escapeRegExp(folderName));
  await page
    .goto(folderUrl, { waitUntil: "domcontentloaded" })
    .catch((error) => {
      const message = error instanceof Error ? error.message : String(error);
      if (!message.includes("is interrupted by another navigation")) {
        throw error;
      }
    });
  await expect
    .poll(
      async () => {
        await page.waitForLoadState("domcontentloaded").catch(() => undefined);

        const hasPublicHeading = await page
          .getByRole("heading", { name: folderName })
          .isVisible()
          .catch(() => false);
        const hasAuthenticatedFolderLabel = await page
          .getByRole("button", { name: folderNamePattern })
          .first()
          .isVisible()
          .catch(() => false);

        return hasPublicHeading || hasAuthenticatedFolderLabel;
      },
      {
        intervals: [500, 1_000, 2_000],
        timeout: 30_000,
      },
    )
    .toBe(true);
};

test("Public folder does not show anonymous CTAs to authenticated users", async ({
  page,
  context,
  isolatedWorkspace,
}) => {
  const folderName = isolatedWorkspace.result.workspace_root.title;
  const folderUrl = await makeScenarioFolderPublic(
    page,
    context,
    folderName,
  );

  await openPublicFolderAsAuthenticated(page, folderUrl, folderName);
  await expect(page.getByTestId("anonymous-cta-login")).not.toBeVisible();
  await expect(page.getByTestId("anonymous-cta-try-out")).not.toBeVisible();
  await expect(page.getByTestId("anonymous-dropdown-menu")).not.toBeVisible();
  await expect(page.getByTestId("my-files-cta")).not.toBeVisible();
});

test("Public folder shows AnonymousCTA and login redirects for anonymous users", async ({
  page,
  context,
  browser,
  isolatedWorkspace,
}) => {
  const folderName = isolatedWorkspace.result.workspace_root.title;
  const folderUrl = await makeScenarioFolderPublic(
    page,
    context,
    folderName,
  );

  const anonContext = await createAnonymousBrowserContext(browser);
  await installClipboardShim(anonContext);
  const anonPage = await anonContext.newPage();
  await forceAnonymousFrontendConfig(anonPage);
  await openAnonymousPublicFolder(anonPage, folderUrl, folderName);

  await expect(anonPage.getByTestId("anonymous-cta-login")).toBeVisible();
  await expect(anonPage.getByTestId("anonymous-cta-try-out")).toBeVisible();
  await expect(anonPage.getByTestId("my-files-cta")).not.toBeVisible();

  await Promise.all([
    anonPage.waitForRequest((request) =>
      request.url().includes("/authenticate/"),
    ),
    anonPage.getByTestId("anonymous-cta-login").click(),
  ]);

  await anonContext.close();
});

test("Public folder anonymous dropdown copies link and switches language", async ({
  page,
  context,
  browser,
  browserName,
  isolatedWorkspace,
}) => {
  if (browserName === "webkit") {
    return;
  }

  const folderName = isolatedWorkspace.result.workspace_root.title;
  const folderUrl = await makeScenarioFolderPublic(
    page,
    context,
    folderName,
  );

  const anonContext = await createAnonymousBrowserContext(browser);
  await grantClipboardPermissions(browserName, anonContext);
  await installClipboardShim(anonContext);
  const anonPage = await anonContext.newPage();
  await forceAnonymousFrontendConfig(anonPage);
  const displayedUrl = await openAnonymousPublicFolder(
    anonPage,
    folderUrl,
    folderName,
  );

  const dropdownTrigger = anonPage.getByTestId("anonymous-dropdown-menu");
  await expect(dropdownTrigger).toBeVisible();

  await dropdownTrigger.click();
  const copyLinkItem = anonPage.getByRole("menuitem", { name: "Copy link" });
  const languagesItem = anonPage.getByRole("menuitem", { name: "Languages" });
  await expect(copyLinkItem).toBeVisible();
  await expect(languagesItem).toBeVisible();

  await copyLinkItem.click();
  await expect
    .poll(() =>
      anonPage.evaluate(() => String((window as any).__e2eClipboardText || "")),
    )
    .toBe(displayedUrl);

  await dropdownTrigger.click();
  await languagesItem.click();
  await expect(
    anonPage.getByRole("menuitem", { name: "Français" }),
  ).toBeVisible();
  await anonPage.getByRole("menuitem", { name: "Français" }).click();
  await expect(anonPage.getByTestId("anonymous-cta-login")).toHaveText(
    "Se connecter",
  );

  await anonContext.close();
});
