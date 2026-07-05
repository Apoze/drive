import { expect, Page } from "@playwright/test";
import { test } from "./fixtures/actors";
import {
  expectRowItem,
  expectRowItemIsNotVisible,
  waitForExplorerGridToSettle,
} from "./utils-embedded-grid";
import { dismissReleaseNotesIfPresent } from "./utils-common";
import { gotoExplorerRoute } from "./utils-explorer";
import { createFolderInCurrentFolder } from "./utils-item";

type ItemListResponse = {
  results?: Array<{
    id: string;
    title: string;
  }>;
};

const getTrashItemIdsByTitle = async (params: {
  apiOrigin: string;
  page: Page;
  titles: string[];
}) => {
  const response = await params.page.request.get(
    `${params.apiOrigin}/api/v1.0/items/trashbin/?page=1&page_size=200`,
  );
  expect(response.ok()).toBeTruthy();
  const data = (await response.json()) as ItemListResponse;

  return params.titles.map((title) => {
    const item = data.results?.find((result) => result.title === title);
    if (!item?.id) {
      throw new Error(`Could not resolve trash item id for ${title}`);
    }
    return item.id;
  });
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

const moveItemsToTrash = async (params: {
  apiOrigin: string;
  page: Page;
  itemIds: string[];
}) => {
  const cookies = await params.page.context().cookies(params.apiOrigin);
  const csrfToken =
    cookies.find((cookie) => cookie.name === "csrftoken")?.value ?? "";
  expect(csrfToken).not.toBe("");

  for (const itemId of params.itemIds) {
    const response = await params.page.request.delete(
      `${params.apiOrigin}/api/v1.0/items/${itemId}/`,
      {
        headers: {
          "X-CSRFToken": csrfToken,
        },
      },
    );
    expect(response.status()).toBe(204);
  }
};

test.setTimeout(90_000);

test("Trash restore partial failure stays local on LAN and keeps trash state coherent", async ({
  page,
}) => {
  const stamp = Date.now();
  const restoredName = `Trash restore ok ${stamp}`;
  const blockedName = `Trash restore blocked ${stamp}`;
  const apiOrigin = process.env.E2E_API_ORIGIN || "http://192.168.10.123:8071";
  const partialFailureDetail = "Injected partial restore failure";

  await page.goto("/");
  await dismissReleaseNotesIfPresent(page, 10_000);

  await page.goto("/explorer/items/my-files");
  await waitForExplorerGridToSettle(page);

  await createFolderInCurrentFolder(page, restoredName);
  await createFolderInCurrentFolder(page, blockedName);
  await expectRowItem(page, restoredName);
  await expectRowItem(page, blockedName);

  const seedIds = await getMyFilesItemIdsByTitle({
    apiOrigin,
    page,
    titles: [restoredName, blockedName],
  });
  await moveItemsToTrash({
    apiOrigin,
    page,
    itemIds: seedIds,
  });

  await page.goto("about:blank");
  await gotoExplorerRoute(page, "/explorer/trash");
  await waitForExplorerGridToSettle(page);
  await expect(page.getByTestId("trash-page-breadcrumbs")).toBeVisible({
    timeout: 20_000,
  });

  const trashUrl = page.url();

  await expectRowItem(page, restoredName);
  await expectRowItem(page, blockedName);

  const [restoredId, blockedId] = await getTrashItemIdsByTitle({
    apiOrigin,
    page,
    titles: [restoredName, blockedName],
  });

  await page.route(`**/api/v1.0/items/${blockedId}/restore/`, async (route) => {
    if (route.request().method() !== "POST") {
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

  const restoredTrashRow = page.locator("tr.selectable").filter({
    has: page.getByRole("button", {
      name: restoredName,
      exact: true,
    }),
  });
  const blockedTrashRow = page.locator("tr.selectable").filter({
    has: page.getByRole("button", {
      name: blockedName,
      exact: true,
    }),
  });

  await expect(restoredTrashRow).toBeVisible({ timeout: 20_000 });
  await expect(blockedTrashRow).toBeVisible({ timeout: 20_000 });
  await restoredTrashRow.click({ modifiers: ["ControlOrMeta"], force: true });
  await blockedTrashRow.click({ modifiers: ["ControlOrMeta"], force: true });

  const selectionBar = page.locator(".explorer__selection-bar");
  await expect(selectionBar).toBeVisible({ timeout: 20_000 });
  await expect(page.locator("tr.selectable.selected")).toHaveCount(2);

  const successRestoreResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/v1.0/items/${restoredId}/restore/`) &&
      response.ok(),
  );
  const failedRestoreResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/v1.0/items/${blockedId}/restore/`) &&
      response.status() === 403,
  );

  await selectionBar
    .getByRole("button", { name: /^(Restore|Restaurer|Herstel)$/i })
    .click();

  await Promise.all([successRestoreResponse, failedRestoreResponse]);
  await expectRowItemIsNotVisible(page, restoredName, { timeoutMs: 30_000 });
  await expectRowItem(page, blockedName, { timeoutMs: 30_000 });

  await expect
    .poll(() => page.url(), { timeout: 20_000 })
    .toBe(trashUrl);
  await expect(
    page
      .locator("nextjs-portal")
      .filter({
        hasText: /Unhandled Runtime Error|Application error|Runtime Error/i,
      }),
  ).toHaveCount(0);

  await expect(page.locator("tr.selectable.selected")).toHaveCount(1);
  await expect(
    page.locator("tr.selectable.selected").filter({
      has: page.getByRole("button", {
        name: blockedName,
        exact: true,
      }),
    }),
  ).toHaveCount(1);

  await expect(
    page.locator(".Toastify__toast").filter({
      hasText: /Item restored|items restored|Élément restauré|éléments restaurés|Item hersteld|items hersteld/i,
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

  await page.unroute(`**/api/v1.0/items/${blockedId}/restore/`);
});
