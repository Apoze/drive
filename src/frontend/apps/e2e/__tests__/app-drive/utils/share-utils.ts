import { Page, expect } from "@playwright/test";
import { clickOnBreadcrumbButtonAction } from "../utils-explorer";

export const getShareModal = async (page: Page) => {
  return page.getByLabel("Share modal");
};

export const expectShareModal = async (page: Page) => {
  const shareModal = await getShareModal(page);
  await expect(shareModal).toBeVisible();
  return shareModal;
};

export const openShareModal = async (page: Page) => {
  await clickOnBreadcrumbButtonAction(page, "Share");
  const shareModal = await expectShareModal(page);
  return shareModal;
};

export const closeShareModal = async (page: Page) => {
  const shareModal = await getShareModal(page);
  await shareModal.getByRole("button", { name: "Close" }).click();
  await expect(shareModal).not.toBeVisible();
  await expect(page.getByTestId("explorer-breadcrumbs")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("create-folder-button")).toBeVisible({
    timeout: 20_000,
  });
};

export const getMemberItem = async (page: Page, userName: string) => {
  const shareModal = await getShareModal(page);
  const membersList = shareModal.getByTestId("members-list");
  const memberItem = membersList
    .getByTestId("share-member-item")
    .filter({ hasText: userName });
  return memberItem;
};

export const expectUserInMembersList = async (
  page: Page,
  userName: string,
  role: string,
) => {
  const memberItem = await getMemberItem(page, userName);
  await expect(memberItem).toBeVisible({ timeout: 20_000 });
  await expect(memberItem).toContainText(role, { timeout: 20_000 });
  return memberItem;
};

export const clickOnMemberItemRole = async (page: Page, userName: string) => {
  const memberItem = await getMemberItem(page, userName);
  await expect(memberItem).toBeVisible();
  const roleDropdown = memberItem.getByTestId("access-role-dropdown-button");
  await expect(roleDropdown).toBeVisible();
  await roleDropdown.click();
};

export const expectAllowedRoles = async (
  page: Page,
  userName: string,
  allowedRoles: string[],
  notAllowedRoles: string[],
) => {
  const memberItem = await getMemberItem(page, userName);
  await expect(memberItem).toBeVisible({ timeout: 20_000 });
  const roleDropdown = memberItem.getByTestId("access-role-dropdown-button");
  await expect(roleDropdown).toBeVisible();
  await roleDropdown.click();

  for (const role of allowedRoles) {
    const roleItem = page.getByRole("menuitem", { name: role });
    await expect(roleItem).toBeVisible();
    await expect(roleItem).toBeEnabled();
  }

  for (const role of notAllowedRoles) {
    const roleItem = page.getByRole("menuitem", { name: role });
    await expect(roleItem).toBeVisible();
    await expect(roleItem).toBeDisabled();
  }
  await closeDropdowns(page);
};

export const selectLinkReach = async (page: Page, linkReach: string) => {
  const linkReachDropdown = page.getByTestId(
    "share-link-reach-dropdown-button",
  );
  await linkReachDropdown.click();
  const linkReachItem = page.getByRole("menuitem", { name: linkReach });
  const updateResponse = page.waitForResponse((response) => {
    const request = response.request();
    return (
      request.method() === "PUT" &&
      response.url().includes("/api/v1.0/items/") &&
      response.url().includes("/link-configuration/") &&
      response.status() >= 200 &&
      response.status() < 300
    );
  });
  await linkReachItem.click();
  await updateResponse;
};

export const expectLinkReachSelected = async (
  page: Page,
  linkReach: string,
) => {
  const linkReachDropdown = page.getByTestId(
    "share-link-reach-dropdown-button",
  );
  await expect(linkReachDropdown).toBeVisible();
  await linkReachDropdown.click();
  const linkReachItem = page.getByRole("menuitem", { name: linkReach });
  await expect(linkReachItem).toBeVisible();
  await expect(linkReachItem).toContainText("check"); // we have the right icon
  await closeDropdowns(page);
};

export const clickCopyLinkButton = async (page: Page) => {
  await page.getByRole("button", { name: "Copy link" }).click();
};

export const closeDropdowns = async (page: Page) => {
  await page.locator("body").click();
};

export const expectAllowedLinkReach = async (
  page: Page,
  allowedLinkReach: string[],
  notAllowedLinkReach: string[],
) => {
  const shareModal = await getShareModal(page);
  const linkReachDropdown = shareModal.getByTestId(
    "share-link-reach-dropdown-button",
  );
  await expect(linkReachDropdown).toBeVisible();
  await linkReachDropdown.click();

  for (const linkReach of allowedLinkReach) {
    const roleItem = page.getByRole("menuitem", { name: linkReach });
    await expect(roleItem).toBeVisible();
    await expect(roleItem).toBeEnabled();
  }

  for (const linkReach of notAllowedLinkReach) {
    const roleItem = page.getByRole("menuitem", { name: linkReach });
    await expect(roleItem).toBeVisible();
    await expect(roleItem).toBeDisabled();
  }
  await closeDropdowns(page);
};

export const getUserSearchResult = async (page: Page, userName: string) => {
  const shareModal = await getShareModal(page);
  const userSearchList = shareModal.getByTestId("search-users-list");
  await expect(userSearchList).toBeVisible();
  const userSearchItem = userSearchList
    .getByTestId("search-user-item")
    .filter({ hasText: userName });
  const searchInput = shareModal.getByRole("combobox", {
    name: "Quick search input",
  });
  const retryUntil = Date.now() + 30_000;

  while (!(await userSearchItem.isVisible().catch(() => false))) {
    if (Date.now() > retryUntil) {
      break;
    }

    const throttledAlert = page
      .getByRole("alert")
      .filter({ hasText: /request was throttled/i })
      .first();
    if (await throttledAlert.isVisible().catch(() => false)) {
      await expect(throttledAlert).not.toBeVisible({ timeout: 5_000 });
      const searchValue = await searchInput.inputValue();
      await searchInput.fill("");
      await searchInput.fill(searchValue);
    }

    await page.waitForTimeout(500);
  }

  return userSearchItem;
};

export const selectRoleUser = async (page: Page, userRole: string) => {
  const shareModal = await getShareModal(page);
  const selectedUsersList = shareModal.getByTestId("selected-users-list");
  await expect(selectedUsersList).toBeVisible();
  await selectedUsersList.getByTestId("access-role-dropdown-button").click();
  await page.getByRole("menuitem", { name: userRole }).click();
};

export const shareCurrentItemWithWebkitUser = async (
  page: Page,
  userRole: string = "Reader",
) => {
  await shareCurrentItemWithUser(page, "user@webkit.test", userRole, "webkit");
};

export const shareCurrentItemWithUser = async (
  page: Page,
  userEmail: string,
  userRole: string = "Reader",
  searchQuery?: string,
  searchResultText?: string,
) => {
  const userSearchText = searchQuery || userEmail;
  const userSearchResultText = searchResultText || userSearchText;
  await clickOnBreadcrumbButtonAction(page, "Share");
  const shareModal = await expectShareModal(page);
  await expect(
    shareModal.getByRole("combobox", { name: "Quick search input" }),
  ).toBeVisible();
  await shareModal
    .getByRole("combobox", { name: "Quick search input" })
    .click();
  await shareModal
    .getByRole("combobox", { name: "Quick search input" })
    .fill(userSearchText);
  const userSearchItem = await getUserSearchResult(page, userSearchResultText);
  await expect(userSearchItem).toBeVisible({ timeout: 20_000 });
  await userSearchItem.click();
  const selectedUsersList = shareModal.getByTestId("selected-users-list");
  await expect(selectedUsersList).toBeVisible();
  await expect(selectedUsersList.getByTestId("selected-user-item")).toHaveCount(1);
  await selectRoleUser(page, userRole);
  await selectedUsersList.getByRole("button", { name: "Share" }).click();
  await expectUserInMembersList(page, userEmail, userRole);
};
