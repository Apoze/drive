import { expect, Page, test } from "@playwright/test";
import {
  clickOnRowItemActions,
  expectRowItem,
  expectRowItemIsNotVisible,
  getRowItem,
} from "./utils-embedded-grid";
import {
  dismissReleaseNotesIfPresent,
  keyCloakSignIn,
} from "./utils-common";
import { createFolderInCurrentFolder } from "./utils-item";
import { expectExplorerShellReady } from "./utils-explorer";

type ItemListResponse = {
  results?: Array<{
    id: string;
    title: string;
  }>;
};

const getMyFilesItemIdsByTitle = async (params: {
  apiOrigin: string;
  page: Page;
  titles: string[];
}) => {
  const response = await params.page.request.get(
    `${params.apiOrigin}/api/v1.0/items/?page=1&page_size=100&ordering=-type,-created_at&is_creator_me=true`,
  );
  expect(response.ok()).toBeTruthy();
  const data = (await response.json()) as ItemListResponse;

  return params.titles.map((title) => {
    const item = data.results?.find((result) => result.title === title);
    if (!item?.id) {
      throw new Error(`Could not resolve item id for ${title}`);
    }
    return item.id;
  });
};

test.setTimeout(90_000);

test("Bulk delete partial failure stays local on LAN and keeps explorer state coherent", async ({
  page,
}) => {
  const stamp = Date.now();
  const deletableName = `Bulk delete ok ${stamp}`;
  const blockedName = `Bulk delete blocked ${stamp}`;
  const apiOrigin = process.env.E2E_API_ORIGIN || "http://192.168.10.123:8071";
  const partialFailureDetail = "Injected partial delete failure";

  await page.goto("/");
  await keyCloakSignIn(page, "drive", "drive");
  await dismissReleaseNotesIfPresent(page, 10_000);

  await page.goto("/explorer/items/my-files");
  await expectExplorerShellReady(page);

  const folderUrl = page.url();

  await createFolderInCurrentFolder(page, deletableName);
  await createFolderInCurrentFolder(page, blockedName);
  await expectRowItem(page, deletableName);
  await expectRowItem(page, blockedName);

  const [deletableId, blockedId] = await getMyFilesItemIdsByTitle({
    apiOrigin,
    page,
    titles: [deletableName, blockedName],
  });

  await page.route(`**/api/v1.0/items/${blockedId}/`, async (route) => {
    if (route.request().method() !== "DELETE") {
      await route.continue();
      return;
    }

    await route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({
        detail: partialFailureDetail,
      }),
    });
  });

  const deletableRow = await getRowItem(page, deletableName);
  const blockedRow = await getRowItem(page, blockedName);

  await clickOnRowItemActions(page, blockedName, "Info");
  const rightPanel = page.getByTestId("right-panel");
  await expect(rightPanel).toBeVisible({ timeout: 20_000 });
  await expect(
    rightPanel.getByText(blockedName, { exact: true }),
  ).toBeVisible({ timeout: 20_000 });

  await deletableRow.click({ modifiers: ["Control"] });
  await blockedRow.click({ modifiers: ["Control"] });

  const selectionBar = page.locator(".explorer__selection-bar");
  await expect(selectionBar).toBeVisible({ timeout: 20_000 });

  const successDeleteResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "DELETE" &&
      response.url().includes(`/api/v1.0/items/${deletableId}/`) &&
      response.status() === 204,
  );
  const failedDeleteResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "DELETE" &&
      response.url().includes(`/api/v1.0/items/${blockedId}/`) &&
      response.status() === 403,
  );

  await selectionBar
    .getByRole("button", { name: /^(Delete|Supprimer)$/i })
    .click();

  await Promise.all([successDeleteResponse, failedDeleteResponse]);
  await expectRowItemIsNotVisible(page, deletableName, { timeoutMs: 30_000 });
  await expectRowItem(page, blockedName, { timeoutMs: 30_000 });

  await expect
    .poll(() => page.url(), { timeout: 20_000 })
    .toBe(folderUrl);
  await expect(
    page
      .locator("nextjs-portal")
      .filter({
        hasText: /Unhandled Runtime Error|Application error|Runtime Error/i,
      }),
  ).toHaveCount(0);

  await expect(page.locator("tr.selectable.selected")).toHaveCount(1);
  await expect(
    page
      .locator("tr.selectable.selected")
      .filter({
        has: page.getByRole("button", {
          name: blockedName,
          exact: true,
        }),
      }),
  ).toHaveCount(1);

  await expect(rightPanel).toBeVisible({ timeout: 20_000 });
  await expect(
    rightPanel.getByText(blockedName, { exact: true }),
  ).toBeVisible({ timeout: 20_000 });
  await expect(
    rightPanel.getByText(deletableName, { exact: true }),
  ).toHaveCount(0);

  await expect(
    page.locator(".Toastify__toast").filter({
      hasText: /Item deleted|items deleted|Élément supprimé|éléments supprimés/i,
    }),
  ).toBeVisible({ timeout: 20_000 });
  await expect(
    page.locator(".Toastify__toast").filter({
      hasText: new RegExp(
        `${blockedName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}.*${partialFailureDetail}`,
        "i",
      ),
    }),
  ).toBeVisible({ timeout: 20_000 });

  await page.unroute(`**/api/v1.0/items/${blockedId}/`);
});
