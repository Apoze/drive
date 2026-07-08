import { expect, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { getE2EBaseURL } from "../../e2e-origins";
import { test as base } from "./fixtures/scenarios";
import type { WorkerActorFixture } from "./fixtures/types";
import {
  clickToFavorites,
  clickToMyFiles,
  clickToRecent,
  clickToSharedWithMe,
  getMainWorkspaceBreadcrumbs,
  navigateToFolder,
  openWorkspaceFromMyFiles,
} from "./utils-navigate";
import { createFolderInCurrentFolder } from "./utils-item";
import { expectRowItem } from "./utils-embedded-grid";
import { expectExplorerBreadcrumbs } from "./utils-explorer";
import { ensureBootstrappedActorSession } from "./utils-common";
import { closeFilePreview } from "./utils-editor";

const E2E_BASE_URL = getE2EBaseURL();

base.setTimeout(60_000);

type TwoUsers = {
  userB: { context: BrowserContext; page: Page };
};

const createActorContext = async (
  browser: Browser,
  actor: WorkerActorFixture,
) => {
  const context = await browser.newContext({
    baseURL: E2E_BASE_URL,
    storageState: actor.storageStatePath,
  });
  const page = await context.newPage();
  await ensureBootstrappedActorSession(page, actor);
  await page.close();
  return context;
};

const MultiUserTest = base.extend<TwoUsers>({
  userB: async ({ browser, secondaryActor, sharedWorkspace }, use) => {
    void sharedWorkspace;
    const context = await createActorContext(browser, secondaryActor);
    try {
      const page = await context.newPage();
      await use({ context, page });
    } finally {
      await context.close();
    }
  },
});

const openNewMenuItem = async (page: Page, menuItem: string | RegExp) => {
  await page
    .getByRole("button", { name: /(New|Nouveau|Create|Créer)$/ })
    .first()
    .click();
  await page.getByRole("menuitem", { name: menuItem }).click();
};

const createFolderViaNewMenu = async (page: Page, folderName: string) => {
  await openNewMenuItem(
    page,
    /^(Create folder|New folder|Créer un dossier|Nouveau dossier)$/i,
  );
  await page
    .getByRole("textbox", { name: /^(Folder name|Nom du dossier)$/i })
    .fill(folderName);
  await page.getByRole("button", { name: /^(Create|Créer)$/ }).click();
};

const closeFilePreviewIfOpen = async (page: Page) => {
  if (await page.getByTestId("file-preview").isVisible().catch(() => false)) {
    await closeFilePreview(page);
  }
};

const createDocumentViaNewMenu = async (page: Page, fileName: string) => {
  await openNewMenuItem(
    page,
    /^(Document \(ODT\)|New text document|Nouveau document texte)$/i,
  );
  const createDialog = page.getByRole("dialog", { name: /Create/i });
  await createDialog
    .locator(".explorer__create-file__modal__filename-input")
    .fill(fileName);
  await Promise.all([
    page.waitForResponse((response) => {
      const request = response.request();
      return (
        request.method() === "POST" &&
        response.url().includes("/api/v1.0/items/") &&
        response.status() >= 200 &&
        response.status() < 300
      );
    }),
    createDialog.getByRole("button", { name: /^(Create|Créer)$/ }).click(),
  ]);
  await expect(createDialog).not.toBeVisible({ timeout: 20_000 });
};

MultiUserTest(
  "+ New from a read-only shared folder falls back to My files",
  async ({ userB, sharedWorkspace }) => {
    const sharedRoot = sharedWorkspace.result.shared_root;
    const fallbackFolderName = `Fallback folder ${sharedWorkspace.scope.scenario_slug}`;
    const fallbackFileName = `Fallback doc ${sharedWorkspace.scope.scenario_slug}`;

    await userB.page.goto("/");
    await clickToSharedWithMe(userB.page);
    await navigateToFolder(userB.page, sharedRoot.title, [
      "Shared with me",
      sharedRoot.title,
    ]);

    await createFolderViaNewMenu(userB.page, fallbackFolderName);

    await expect(userB.page).toHaveURL(/\/explorer\/items\/[0-9a-f-]+$/);
    await expectExplorerBreadcrumbs(userB.page, [
      "My files",
      fallbackFolderName,
    ]);
    await clickToMyFiles(userB.page);
    await expectRowItem(userB.page, fallbackFolderName);

    await clickToSharedWithMe(userB.page);
    await navigateToFolder(userB.page, sharedRoot.title, [
      "Shared with me",
      sharedRoot.title,
    ]);

    await createDocumentViaNewMenu(userB.page, fallbackFileName);

    await expect(userB.page).toHaveURL(/\/explorer\/items\/my-files$/);
    await expectExplorerBreadcrumbs(userB.page, ["My files"]);
    await expect
      .poll(
        async () => {
          await closeFilePreviewIfOpen(userB.page);
          return userB.page
            .getByRole("button", {
              name: `${fallbackFileName}.odt`,
              exact: true,
            })
            .last()
            .isVisible()
            .catch(() => false);
        },
        { timeout: 60_000 },
      )
      .toBe(true);
    await expectRowItem(userB.page, `${fallbackFileName}.odt`, {
      timeoutMs: 60_000,
    });
  },
);

const virtualTabs: Array<{
  go: (page: Page) => Promise<void>;
  label: string;
}> = [
  { go: clickToRecent, label: "Recent" },
  { go: clickToSharedWithMe, label: "Shared" },
  { go: clickToFavorites, label: "Starred" },
];

for (const { go, label } of virtualTabs) {
  base(`+ New from ${label} creates in My files`, async ({
    page,
    isolatedWorkspace,
  }) => {
    const folderName = `Tab folder ${label} ${isolatedWorkspace.scope.scenario_slug}`;

    await page.goto("/");
    await go(page);
    await createFolderViaNewMenu(page, folderName);

    await expectExplorerBreadcrumbs(page, ["My files", folderName]);
    await clickToMyFiles(page);
    await expectRowItem(page, folderName);
  });
}

base("+ New inside a writable folder still creates in place", async ({
  page,
  isolatedWorkspace,
}) => {
  const rootTitle = isolatedWorkspace.result.workspace_root.title;
  const parentName = `Writable parent ${isolatedWorkspace.scope.scenario_slug}`;

  await page.goto("/");
  await openWorkspaceFromMyFiles(page, rootTitle);
  await createFolderInCurrentFolder(page, parentName);
  await navigateToFolder(
    page,
    parentName,
    getMainWorkspaceBreadcrumbs(rootTitle, parentName),
  );

  await createFolderViaNewMenu(page, "Child");

  await expectExplorerBreadcrumbs(page, [
    "My files",
    "My files",
    rootTitle,
    parentName,
  ]);
  await expectRowItem(page, "Child");
});
