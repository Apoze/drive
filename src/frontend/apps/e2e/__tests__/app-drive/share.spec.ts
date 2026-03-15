import { expect, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { test as base } from "./fixtures/scenarios";
import {
  clickToSharedWithMe,
  getMainWorkspaceBreadcrumbs,
  navigateToFolder,
  openMainWorkspaceFromMyFiles,
} from "./utils-navigate";
import { createFolderInCurrentFolder } from "./utils-item";
import { ensureBootstrappedActorSession } from "./utils-common";
import {
  clickCopyLinkButton,
  clickOnMemberItemRole,
  closeShareModal,
  expectAllowedLinkReach,
  expectAllowedRoles,
  expectLinkReachSelected,
  openShareModal,
  selectLinkReach,
  shareCurrentItemWithUser,
} from "./utils/share-utils";
import {
  expectRowItem,
  expectRowItemIsNotVisible,
} from "./utils-embedded-grid";
import {
  clickOnBreadcrumbButtonAction,
  expectExplorerBreadcrumbs,
} from "./utils-explorer";
import { setupPosthogEventCapture } from "./utils/posthog-utils";
import type { WorkerActorFixture } from "./fixtures/types";

const E2E_BASE_URL = process.env.E2E_BASE_URL || "http://127.0.0.1:3000";

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

type TwoUsers = {
  userA: { context: BrowserContext; page: Page };
  userB: { context: BrowserContext; page: Page };
  shareFolderName: string;
  shareSubFolderName: string;
  shareTargetEmail: string;
  shareTargetSearchResultText: string;
};

const MultiUserTest = base.extend<TwoUsers>({
  userA: async ({ context, page, primaryActor, sharedWorkspace }, use) => {
    void sharedWorkspace;
    await ensureBootstrappedActorSession(page, primaryActor);
    await use({ context, page });
  },

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

  shareTargetEmail: async ({ secondaryActor }, use) => {
    await use(secondaryActor.actor.email);
  },

  shareTargetSearchResultText: async ({ secondaryActor }, use) => {
    await use(
      secondaryActor.actor.full_name ||
        secondaryActor.actor.short_name ||
        secondaryActor.actor.email,
    );
  },

  shareFolderName: async ({ sharedWorkspace }, use) => {
    await use(`Folder ${sharedWorkspace.scope.scenario_slug}`);
  },

  shareSubFolderName: async ({ sharedWorkspace }, use) => {
    await use(`Sub folder ${sharedWorkspace.scope.scenario_slug}`);
  },
});

MultiUserTest("Share folder with user", async ({
  userA,
  userB,
  shareFolderName,
  shareTargetEmail,
  shareTargetSearchResultText,
}, testInfo) => {
  testInfo.setTimeout(120000);

  // User A creates a folder and shares it with User B
  await userA.page.goto("/");
  await openMainWorkspaceFromMyFiles(userA.page);
  await createFolderInCurrentFolder(userA.page, shareFolderName);

  // User B navigates to the shared with me folder and expects the folder to be not visible
  await userB.page.goto("/");
  await clickToSharedWithMe(userB.page);
  await expectRowItemIsNotVisible(userB.page, shareFolderName);

  // User A navigates to the folder and shares it with User B
  await navigateToFolder(
    userA.page,
    shareFolderName,
    getMainWorkspaceBreadcrumbs(shareFolderName),
  );
  await shareCurrentItemWithUser(
    userA.page,
    shareTargetEmail,
    "Reader",
    shareTargetEmail,
    shareTargetSearchResultText,
  );

  // User B navigates to the shared with me folder and expects the folder to be visible
  await userB.page.goto("/");
  await clickToSharedWithMe(userB.page);
  await expectRowItem(userB.page, shareFolderName);
});

MultiUserTest(
  "share a folder and a sub folder with user and verify the roles",
  async ({
    userA,
    shareFolderName,
    shareSubFolderName,
    shareTargetEmail,
    shareTargetSearchResultText,
  }) => {
    // User A creates a folder and shares it with User B
    await userA.page.goto("/");
    await openMainWorkspaceFromMyFiles(userA.page);
    await createFolderInCurrentFolder(userA.page, shareFolderName);
    await navigateToFolder(
      userA.page,
      shareFolderName,
      getMainWorkspaceBreadcrumbs(shareFolderName),
    );
    await shareCurrentItemWithUser(
      userA.page,
      shareTargetEmail,
      "Editor",
      shareTargetEmail,
      shareTargetSearchResultText,
    );
    await closeShareModal(userA.page);
    await createFolderInCurrentFolder(userA.page, shareSubFolderName);
    await navigateToFolder(
      userA.page,
      shareSubFolderName,
      getMainWorkspaceBreadcrumbs(shareFolderName, shareSubFolderName),
    );
    await clickOnBreadcrumbButtonAction(userA.page, "Share");

    await expectAllowedRoles(
      userA.page,
      shareTargetEmail,
      ["Editor", "Administrator", "Owner"],
      ["Reader"],
    );
  },
);

MultiUserTest(
  "share a folder and verify the link reach",
  async ({
    userA,
    shareFolderName,
    shareSubFolderName,
  }) => {
    // User A creates a folder and shares it with User B
    await userA.page.goto("/");
    await openMainWorkspaceFromMyFiles(userA.page);
    await createFolderInCurrentFolder(userA.page, shareFolderName);
    await navigateToFolder(
      userA.page,
      shareFolderName,
      getMainWorkspaceBreadcrumbs(shareFolderName),
    );
    await openShareModal(userA.page);
    await selectLinkReach(userA.page, "Connected");
    await expectLinkReachSelected(userA.page, "Connected");
    await closeShareModal(userA.page);
    await createFolderInCurrentFolder(userA.page, shareSubFolderName);
    await navigateToFolder(
      userA.page,
      shareSubFolderName,
      getMainWorkspaceBreadcrumbs(shareFolderName, shareSubFolderName),
    );
    await openShareModal(userA.page);
    await expectLinkReachSelected(userA.page, "Connected");
    await expectAllowedLinkReach(
      userA.page,
      ["Connected", "Public"],
      ["Private"],
    );
  },
);

MultiUserTest("share a folder and posthog event is sent", async ({
  userA,
  shareFolderName,
}) => {
  const { expectEventSent } = await setupPosthogEventCapture(userA.page);

  // User A creates a folder and shares it with User B
  await userA.page.goto("/");
  await openMainWorkspaceFromMyFiles(userA.page);
  await createFolderInCurrentFolder(userA.page, shareFolderName);
  await navigateToFolder(
    userA.page,
    shareFolderName,
    getMainWorkspaceBreadcrumbs(shareFolderName),
  );
  await openShareModal(userA.page);
  await selectLinkReach(userA.page, "Connected");
  await expectLinkReachSelected(userA.page, "Connected");
  await clickCopyLinkButton(userA.page);
  await expectEventSent("click_copy_link");
});

MultiUserTest(
  "click parent folder link in share modal navigates to parent",
  async ({
    userA,
    shareFolderName,
    shareSubFolderName,
    shareTargetEmail,
    shareTargetSearchResultText,
  }) => {
    const { expectEventSent } = await setupPosthogEventCapture(userA.page);

    // User A creates a folder, shares it, and creates a sub folder
    await userA.page.goto("/");
    await openMainWorkspaceFromMyFiles(userA.page);
    await createFolderInCurrentFolder(userA.page, shareFolderName);
    await navigateToFolder(
      userA.page,
      shareFolderName,
      getMainWorkspaceBreadcrumbs(shareFolderName),
    );
    await shareCurrentItemWithUser(
      userA.page,
      shareTargetEmail,
      "Editor",
      shareTargetEmail,
      shareTargetSearchResultText,
    );
    await closeShareModal(userA.page);
    await createFolderInCurrentFolder(userA.page, shareSubFolderName);
    await navigateToFolder(
      userA.page,
      shareSubFolderName,
      getMainWorkspaceBreadcrumbs(shareFolderName, shareSubFolderName),
    );

    // Open share modal on the sub folder and click the parent folder link
    const shareModal = await openShareModal(userA.page);
    await clickOnMemberItemRole(userA.page, shareTargetEmail);
    const parentFolderLink = userA.page.getByRole("button", {
      name: "the parent folder.",
    });
    await expect(parentFolderLink).toBeVisible();
    await parentFolderLink.click();

    // The share modal should close and the user should be redirected to the parent
    await expect(shareModal).not.toBeVisible();
    await expectExplorerBreadcrumbs(
      userA.page,
      getMainWorkspaceBreadcrumbs(shareFolderName),
    );

    // Verify the posthog click_redirect_to_parent_item event was sent
    await expectEventSent("click_redirect_to_parent_item");
  },
);
