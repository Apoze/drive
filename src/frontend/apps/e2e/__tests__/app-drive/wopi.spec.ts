import path from "path";
import { expect, Page } from "@playwright/test";
import { test } from "./fixtures/scenarios";
import {
  clickOnRowItemActions,
  getRowItem,
} from "./utils-embedded-grid";
import { openWorkspaceFromMyFiles } from "./utils-navigate";
import {
  closeFilePreview,
  createEditorFileFromMoreFormats,
  openWopiEditorFromPreview,
  waitForEditorFrame,
} from "./utils-editor";
import { uploadFile } from "./utils/upload-utils";
import { grantClipboardPermissions } from "./utils/various-utils";

const DOCX_FILE_PATH = path.join(__dirname, "assets", "empty_doc.docx");

const mockRequiresConversion = async (
  page: Page,
  options: {
    placeholder?: Record<string, unknown> | (() => Record<string, unknown> | undefined);
  } = {},
) => {
  await page.route(
    (url) => /\/api\/v1\.0\/items(\/|$)/.test(url.pathname),
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }

      const placeholder =
        typeof options.placeholder === "function"
          ? options.placeholder()
          : options.placeholder;
      const requestUrl = new URL(route.request().url());
      if (
        placeholder &&
        typeof placeholder.id === "string" &&
        requestUrl.pathname.endsWith(`/api/v1.0/items/${placeholder.id}/`)
      ) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(placeholder),
        });
        return;
      }

      const response = await route.fetch();
      const json = await response.json();
      const inject = (item: Record<string, unknown>) => {
        item.abilities = {
          ...(item.abilities as Record<string, unknown>),
          convert: true,
        };
      };

      if (Array.isArray(json?.results)) {
        json.results.forEach(inject);
        if (placeholder) {
          json.results.push(placeholder);
        }
      } else if (json?.id) {
        inject(json);
      }

      await route.fulfill({ response, json });
    },
  );
};

test("A regular file with convert ability exposes an explicit conversion action", async ({
  page,
  browserName,
  isolatedWorkspace,
}) => {
  test.skip(browserName !== "chromium", "Only runs on chromium");
  test.setTimeout(120_000);
  await mockRequiresConversion(page);
  await page.goto("/");
  await openWorkspaceFromMyFiles(
    page,
    isolatedWorkspace.result.workspace_root.title,
    isolatedWorkspace.result.workspace_root.id,
  );

  await uploadFile(page, DOCX_FILE_PATH);
  await getRowItem(page, "empty_doc.docx");
  await clickOnRowItemActions(page, "empty_doc.docx", "Convert");

  await expect(
    page.getByRole("dialog", { name: "Convert to open this file" }),
  ).toBeVisible();
});

test("Confirming legacy conversion shows the converting placeholder", async ({
  page,
  browserName,
  isolatedWorkspace,
}) => {
  test.skip(browserName !== "chromium", "Only runs on chromium");
  test.setTimeout(120_000);

  const placeholderId = "00000000-0000-0000-0000-000000000001";
  const placeholder = {
    id: placeholderId,
    title: "empty_doc (converted).docx",
    filename: "empty_doc (converted).docx",
    type: "file",
    upload_state: "converting",
    abilities: {},
  };
  let includePlaceholder = false;
  await mockRequiresConversion(page, {
    placeholder: () => (includePlaceholder ? placeholder : undefined),
  });
  await page.route("**/api/v1.0/items/*/convert/", async (route) => {
    includePlaceholder = true;
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(placeholder),
    });
  });

  await page.goto("/");
  await openWorkspaceFromMyFiles(
    page,
    isolatedWorkspace.result.workspace_root.title,
    isolatedWorkspace.result.workspace_root.id,
  );

  await uploadFile(page, DOCX_FILE_PATH);
  await getRowItem(page, "empty_doc.docx");
  await clickOnRowItemActions(page, "empty_doc.docx", "Convert");
  await expect(
    page.getByRole("dialog", { name: "Convert to open this file" }),
  ).toBeVisible();

  const [convertResponse] = await Promise.all([
    page.waitForResponse((response) => {
      const request = response.request();
      return (
        request.method() === "POST" &&
        response.url().endsWith("/convert/") &&
        response.status() === 201
      );
    }),
    page.getByRole("button", { name: "Convert" }).click(),
  ]);
  await expect(convertResponse.json()).resolves.toMatchObject({
    title: placeholder.title,
    upload_state: "converting",
  });
  await expect(
    page.getByRole("dialog", { name: "Convert to open this file" }),
  ).not.toBeVisible({ timeout: 10_000 });
  const convertingRow = page
    .getByRole("row")
    .filter({ hasText: placeholder.title })
    .first();
  await expect(convertingRow).toBeVisible({ timeout: 60_000 });

  const convertingLabel = convertingRow
    .locator(".explorer__grid__item__name__duplicating-label")
    .filter({ hasText: /Conversion in progress/ });
  const sawTransientLabel = await expect(convertingLabel)
    .toBeVisible({ timeout: 5_000 })
    .then(() => true)
    .catch(() => false);

  if (!sawTransientLabel) {
    await expect(convertingRow).toContainText(placeholder.title);
  }
});

test("Wopi editor", async ({ page, context, browserName, isolatedWorkspace }) => {
  test.skip(browserName !== "chromium", "Only runs on chromium");
  test.setTimeout(120_000);
  await grantClipboardPermissions(browserName, context);
  await page.goto("/");
  await openWorkspaceFromMyFiles(page, isolatedWorkspace.result.workspace_root.title);

  const filePreview = await createEditorFileFromMoreFormats({
    page,
    stem: `wopi-odt-${isolatedWorkspace.scope.scenario_slug}`,
    kindLabel: "Text document",
    extensionLabelRegex: /\.odt\b/i,
  });
  await expect(filePreview.getByText("Open in editor")).toBeVisible({
    timeout: 20_000,
  });

  const wopiPage = await openWopiEditorFromPreview({ page, filePreview });
  await waitForEditorFrame({
    filePreview: wopiPage.locator("body"),
    iframe: wopiPage.locator('iframe[name="office_frame"]'),
    timeoutMs: 90_000,
  });

  await wopiPage.close();
  await closeFilePreview(page);
});
