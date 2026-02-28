import test, { expect, Page } from "@playwright/test";
import { clearDb, dismissReleaseNotesIfPresent, login } from "./utils-common";
import { openMainWorkspaceFromMyFiles } from "./utils-navigate";

const openCreateFileModal = async (page: Page) => {
  await page.getByRole("button", { name: "Create" }).first().click({ force: true });
  await page.getByRole("menuitem", { name: "Create a file" }).click();
  const dialog = page.getByRole("dialog", { name: "Create a new file" });
  await expect(dialog).toBeVisible();
  return dialog;
};

const createAndWaitWopi = async ({
  page,
  stem,
  kindLabel,
  extensionLabelRegex,
  expectedFilename,
}: {
  page: Page;
  stem: string;
  kindLabel: "Text document" | "Spreadsheet" | "Presentation";
  extensionLabelRegex: RegExp;
  expectedFilename: string;
}) => {
  const dialog = await openCreateFileModal(page);

  await dialog.locator(".explorer__create-file__modal__filename-input").fill(stem);

  await dialog.getByRole("button", { name: kindLabel }).click();
  await dialog.getByRole("button", { name: extensionLabelRegex }).click();

  const start = Date.now();
  await dialog.getByRole("button", { name: "Create" }).click();

  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible({ timeout: 20000 });

  // The "Loading document..." placeholder is not guaranteed to appear in all envs/browsers,
  // especially when ONLYOFFICE loads quickly. Treat it as optional and wait for the iframe.
  const loading = filePreview.getByText("Loading document...");
  const loadingWasVisible = await loading.isVisible().catch(() => false);
  if (loadingWasVisible) {
    await expect(loading).toBeHidden({ timeout: 60000 });
  }

  const editorFrame = filePreview.locator("iframe");
  await expect(editorFrame).toBeVisible({ timeout: 60000 });

  const firstOpenMs = Date.now() - start;
  console.log(`wopi_onlyoffice_first_open_ms file=${expectedFilename} ms=${firstOpenMs}`);

  // Close preview
  await filePreview.getByRole("button", { name: "close" }).click();
  await expect(filePreview).toBeHidden({ timeout: 10000 });
};

test.setTimeout(2 * 60 * 1000);

test("ONLYOFFICE editnew: new OOXML loads fast", async ({ page }) => {
  await clearDb();
  await login(page, "drive@example.com");

  await page.goto("/");
  await dismissReleaseNotesIfPresent(page, 10_000);
  await openMainWorkspaceFromMyFiles(page);

  const stamp = `${Date.now()}`;

  await createAndWaitWopi({
    page,
    stem: `onlyoffice-editnew-docx-${stamp}`,
    kindLabel: "Text document",
    extensionLabelRegex: /\.docx\b/i,
    expectedFilename: `onlyoffice-editnew-docx-${stamp}.docx`,
  });

  await createAndWaitWopi({
    page,
    stem: `onlyoffice-editnew-xlsx-${stamp}`,
    kindLabel: "Spreadsheet",
    extensionLabelRegex: /\.xlsx\b/i,
    expectedFilename: `onlyoffice-editnew-xlsx-${stamp}.xlsx`,
  });

  await createAndWaitWopi({
    page,
    stem: `onlyoffice-editnew-pptx-${stamp}`,
    kindLabel: "Presentation",
    extensionLabelRegex: /\.pptx\b/i,
    expectedFilename: `onlyoffice-editnew-pptx-${stamp}.pptx`,
  });
});
