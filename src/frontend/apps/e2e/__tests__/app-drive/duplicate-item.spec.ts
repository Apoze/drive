import { expect, type Page, type Route } from "@playwright/test";
import { test } from "./fixtures/scenarios";
import { openFolderFromMainWorkspace } from "./utils-navigate";
import {
  createFileFromTemplate,
  createFolderInCurrentFolder,
} from "./utils-item";
import {
  clickOnRowItemActions,
  expectRowItem,
  getRowItemActions,
} from "./utils-embedded-grid";

const duplicateLabel = /^(Duplicate|Dupliquer|Dupliceren)$/i;

const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const setupDuplicatingItemRoutes = async (page: Page, parentId: string) => {
  let pendingCopy: Record<string, unknown> | null = null;
  let detailPollCount = 0;

  await page.route("**/api/v1.0/items/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;

    if (request.method() === "POST" && pathname.endsWith("/duplicate/")) {
      const sourceId = pathname.split("/").at(-3);
      if (!sourceId) {
        await route.fallback();
        return;
      }
      const sourceUrl = new URL(request.url());
      sourceUrl.pathname = `/api/v1.0/items/${sourceId}/`;
      const sourceResponse = await route.fetch({
        url: sourceUrl.toString(),
        method: "GET",
      });
      const source = await sourceResponse.json();
      const copyId = `11111111-1111-4111-8111-${sourceId.replaceAll("-", "").slice(0, 12)}`;
      pendingCopy = {
        ...source,
        id: copyId,
        title: `Copy of ${source.title}`,
        upload_state: "duplicating",
      };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        json: pendingCopy,
      });
      return;
    }

    if (
      request.method() === "GET" &&
      pendingCopy &&
      pathname === `/api/v1.0/items/${pendingCopy.id}/`
    ) {
      detailPollCount += 1;
      pendingCopy = {
        ...pendingCopy,
        upload_state: detailPollCount >= 2 ? "ready" : "duplicating",
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        json: pendingCopy,
      });
      return;
    }

    if (
      request.method() === "GET" &&
      pendingCopy &&
      pathname === `/api/v1.0/items/${parentId}/children/`
    ) {
      const response = await route.fetch();
      const json = await response.json();
      const results = Array.isArray(json.results) ? json.results : [];
      const withoutCopy = results.filter(
        (item: { id?: string }) => item.id !== pendingCopy?.id,
      );
      await route.fulfill({
        response,
        json: {
          ...json,
          count: Math.max(json.count ?? 0, withoutCopy.length + 1),
          results: [pendingCopy, ...withoutCopy],
        },
      });
      return;
    }

    await route.fallback();
  });
};

test.describe("Duplicate item", () => {
  test.beforeEach(async ({ page, isolatedWorkspace }) => {
    await page.goto("/");
    await openFolderFromMainWorkspace(
      page,
      isolatedWorkspace.result.workspace_root.title,
      isolatedWorkspace.result.workspace_root.id,
    );
  });

  test("duplicates a regular file and transitions out of duplicating state", async ({
    page,
    isolatedWorkspace,
  }) => {
    const fileName = `DuplicateDoc-${isolatedWorkspace.scope.scenario_slug}`;
    const fileDisplayName = `${fileName}.odt`;
    const copyDisplayName = `Copy of ${fileDisplayName}`;

    await createFileFromTemplate(page, fileName);
    await setupDuplicatingItemRoutes(
      page,
      isolatedWorkspace.result.workspace_root.id,
    );

    const duplicateResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1.0/items/") &&
        response.url().endsWith("/duplicate/") &&
        response.status() === 201,
    );
    await clickOnRowItemActions(page, fileDisplayName, duplicateLabel);
    await duplicateResponse;

    const copyRow = page
      .getByRole("row", {
        name: new RegExp(escapeRegExp(copyDisplayName)),
      })
      .first();
    await expect(copyRow).toBeVisible({ timeout: 20_000 });
    await expect(copyRow).toHaveClass(/duplicating/, { timeout: 10_000 });
    await expect(copyRow).toContainText(/Duplication in progress/i);
    await expect(
      copyRow.locator(".explorer__grid__item__name__spinner"),
    ).toBeVisible();

    await expect(copyRow).not.toHaveClass(/duplicating/, { timeout: 20_000 });
    await expectRowItem(page, copyDisplayName, { timeoutMs: 20_000 });
  });

  test("hides duplicate for folders", async ({ page, isolatedWorkspace }) => {
    const folderName = `DuplicateFolder-${isolatedWorkspace.scope.scenario_slug}`;
    await createFolderInCurrentFolder(page, folderName);

    const folderActions = await getRowItemActions(page, folderName);
    await folderActions.click({ force: true });

    await expect(
      page.getByRole("menuitem", { name: duplicateLabel }),
    ).toHaveCount(0);
  });

  test("shows a focused error toast when regular duplicate fails", async ({
    page,
    isolatedWorkspace,
  }) => {
    const fileName = `DuplicateError-${isolatedWorkspace.scope.scenario_slug}`;
    const fileDisplayName = `${fileName}.odt`;
    await createFileFromTemplate(page, fileName);

    await page.route("**/api/v1.0/items/*/duplicate/", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        json: {
          type: "server_error",
          errors: [
            {
              attr: null,
              code: "error",
              detail: "duplicate failed",
            },
          ],
        },
      });
    });

    await clickOnRowItemActions(page, fileDisplayName, duplicateLabel);

    await expect(page.getByText("Failed to duplicate item.")).toBeVisible({
      timeout: 10_000,
    });
  });
});
