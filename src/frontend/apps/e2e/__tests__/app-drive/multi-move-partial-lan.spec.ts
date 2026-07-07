import { expect, Page, test } from "@playwright/test";
import {
  expectRowItem,
  expectRowItemIsNotVisible,
  getRowItem,
} from "./utils-embedded-grid";
import {
  dismissReleaseNotesIfPresent,
  keyCloakSignIn,
} from "./utils-common";
import { createFolderInCurrentFolder } from "./utils-item";
import { expectExplorerShellReady, gotoExplorerRoute } from "./utils-explorer";

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

test("Items multi-move partial failure stays local on LAN and keeps explorer state coherent", async ({
  page,
}) => {
  const stamp = Date.now();
  const movedName = `Move ok ${stamp}`;
  const blockedName = `Move blocked ${stamp}`;
  const targetName = `Move target ${stamp}`;
  const apiOrigin = process.env.E2E_API_ORIGIN || "http://192.168.10.123:8071";
  const partialFailureDetail = "Injected partial move failure";

  await page.goto("/");
  await keyCloakSignIn(page, "drive", "drive");
  await dismissReleaseNotesIfPresent(page, 10_000);

  await gotoExplorerRoute(page, "/explorer/items/my-files");
  await expectExplorerShellReady(page);

  const rootUrl = page.url();

  await createFolderInCurrentFolder(page, movedName);
  await createFolderInCurrentFolder(page, blockedName);
  await createFolderInCurrentFolder(page, targetName);
  await expectRowItem(page, movedName);
  await expectRowItem(page, blockedName);
  await expectRowItem(page, targetName);

  const [movedId, blockedId, targetId] = await getMyFilesItemIdsByTitle({
    apiOrigin,
    page,
    titles: [movedName, blockedName, targetName],
  });

  await page.route(`**/api/v1.0/items/${blockedId}/move/`, async (route) => {
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

  const movedRow = await getRowItem(page, movedName);
  const blockedRow = await getRowItem(page, blockedName);

  await movedRow.click({ modifiers: ["Control"] });
  await blockedRow.click({ modifiers: ["Control"] });

  const selectionBar = page.locator(".explorer__selection-bar");
  await expect(selectionBar).toBeVisible({ timeout: 20_000 });
  await selectionBar
    .getByRole("button", { name: /^(Move|Déplacer|Verplaatsen)$/i })
    .click();

  const moveModal = page.getByLabel(
    /Move folder modal|Modal de déplacement de dossier|Map verplaatsen modal/i,
  );
  await expect(moveModal).toBeVisible({ timeout: 20_000 });

  const targetRow = moveModal
    .getByRole("row", {
      name: new RegExp(`^${targetName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i"),
    })
    .first();
  await expect(targetRow).toBeVisible({ timeout: 20_000 });
  await targetRow.click();

  const successMoveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/v1.0/items/${movedId}/move/`) &&
      response.ok(),
  );
  const failedMoveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/v1.0/items/${blockedId}/move/`) &&
      response.status() === 403,
  );

  await moveModal
    .getByRole("button", {
      name: /^(Move here|Déplacer ici|Hierheen verplaatsen)$/i,
    })
    .click();

  const moveConfirmationModal = page.getByLabel(
    /Move confirmation modal|Modal de confirmation de déplacement|Verplaatsen bevestigingsmodal/i,
  );
  if (await moveConfirmationModal.isVisible().catch(() => false)) {
    await moveConfirmationModal
      .getByRole("button", {
        name: /^(Move anyway|Déplacer quand même)$/i,
      })
      .click();
  }

  await Promise.all([successMoveResponse, failedMoveResponse]);
  await expect(moveModal).toBeHidden({ timeout: 20_000 });
  await expectRowItemIsNotVisible(page, movedName, { timeoutMs: 30_000 });
  await expectRowItem(page, blockedName, { timeoutMs: 30_000 });

  await expect
    .poll(() => page.url(), { timeout: 20_000 })
    .toBe(rootUrl);
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
      hasText: /item moved|items moved|élément déplacé|éléments déplacés|item verplaatst|items verplaatst/i,
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

  await gotoExplorerRoute(page, `/explorer/items/${targetId}`);
  await expectExplorerShellReady(page);
  await expectRowItem(page, movedName, { timeoutMs: 30_000 });
  await expectRowItemIsNotVisible(page, blockedName, { timeoutMs: 30_000 });

  await page.unroute(`**/api/v1.0/items/${blockedId}/move/`);
});
