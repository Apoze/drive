import { expect, Page, test } from "@playwright/test";
import {
  expectRowItem,
  expectRowItemIsNotVisible,
  getRowItem,
  waitForExplorerGridToSettle,
} from "./utils-embedded-grid";
import {
  dismissReleaseNotesIfPresent,
  keyCloakSignIn,
} from "./utils-common";
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
  await keyCloakSignIn(page, "drive", "drive");
  await dismissReleaseNotesIfPresent(page, 10_000);

  await page.goto("/explorer/items/my-files");
  await waitForExplorerGridToSettle(page);

  await createFolderInCurrentFolder(page, restoredName);
  await createFolderInCurrentFolder(page, blockedName);
  await expectRowItem(page, restoredName);
  await expectRowItem(page, blockedName);

  const restoredRow = await getRowItem(page, restoredName);
  const blockedSeedRow = await getRowItem(page, blockedName);
  await restoredRow.click({ modifiers: ["Control"] });
  await blockedSeedRow.click({ modifiers: ["Control"] });

  const seedSelectionBar = page.locator(".explorer__selection-bar");
  await expect(seedSelectionBar).toBeVisible({ timeout: 20_000 });
  await seedSelectionBar
    .getByRole("button", { name: /^(Delete|Supprimer)$/i })
    .click();

  await expectRowItemIsNotVisible(page, restoredName, { timeoutMs: 30_000 });
  await expectRowItemIsNotVisible(page, blockedName, { timeoutMs: 30_000 });

  await page.goto("/explorer/trash");
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
  await restoredTrashRow.click({ modifiers: ["Control"], force: true });
  await blockedTrashRow.click({ modifiers: ["Control"], force: true });

  const selectionBar = page.locator(".explorer__selection-bar");
  await expect(selectionBar).toBeVisible({ timeout: 20_000 });

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
