import { expect } from "@playwright/test";
import { test } from "./fixtures/scenarios";
import { openFolderFromMainWorkspace } from "./utils-navigate";
import {
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

const makeScenarioFolderPublic = async (
  page: Parameters<typeof openFolderFromMainWorkspace>[0],
  folderName: string,
) => {
  await page.goto("/");
  await openFolderFromMainWorkspace(page, folderName);
  await dismissReleaseNotesIfPresent(page);
  await openShareModal(page);
  await selectLinkReach(page, "Public");
  await closeShareModal(page);
  return page.url();
};

test("Public folder does not show anonymous CTAs to authenticated users", async ({
  page,
  isolatedWorkspace,
}) => {
  const folderUrl = await makeScenarioFolderPublic(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );

  await page.goto(folderUrl, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("anonymous-cta-login")).not.toBeVisible();
  await expect(page.getByTestId("anonymous-cta-try-out")).not.toBeVisible();
  await expect(page.getByTestId("anonymous-dropdown-menu")).not.toBeVisible();
  await expect(page.getByTestId("my-files-cta")).not.toBeVisible();
});

test("Public folder shows AnonymousCTA and login redirects for anonymous users", async ({
  page,
  browser,
  isolatedWorkspace,
}) => {
  const folderUrl = await makeScenarioFolderPublic(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );

  const anonContext = await createAnonymousBrowserContext(browser);
  await installClipboardShim(anonContext);
  const anonPage = await anonContext.newPage();
  await forceAnonymousFrontendConfig(anonPage);
  await anonPage.goto(folderUrl, { waitUntil: "domcontentloaded" });

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
  browser,
  browserName,
  isolatedWorkspace,
}) => {
  if (browserName === "webkit") {
    return;
  }

  const folderUrl = await makeScenarioFolderPublic(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );

  const anonContext = await createAnonymousBrowserContext(browser);
  await grantClipboardPermissions(browserName, anonContext);
  await installClipboardShim(anonContext);
  const anonPage = await anonContext.newPage();
  await forceAnonymousFrontendConfig(anonPage);
  await anonPage.goto(folderUrl, { waitUntil: "domcontentloaded" });

  const dropdownTrigger = anonPage.getByTestId("anonymous-dropdown-menu");
  await expect(dropdownTrigger).toBeVisible();
  const displayedUrl = anonPage.url();

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
