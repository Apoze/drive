import test, { expect, Page } from "@playwright/test";
import { clearDb, dismissReleaseNotesIfPresent, login } from "./utils-common";
import { openMainWorkspaceFromMyFiles } from "./utils-navigate";

const openCreateFileModal = async (page: Page) => {
  await page.getByRole("button", { name: "Create" }).first().click({ force: true });
  await page.getByRole("menuitem", { name: "More formats..." }).click();
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
  const retry = filePreview
    .getByRole("link", { name: /retry/i })
    .or(filePreview.getByRole("button", { name: /retry/i }));

  // ONLYOFFICE can occasionally fail to load and display a Retry action instead of an iframe.
  // Avoid flakiness by retrying within the same bounded wait window (no fixed sleeps).
  const deadlineMs = Date.now() + 60_000;
  let retries = 0;
  while (Date.now() < deadlineMs) {
    if (await editorFrame.first().isVisible().catch(() => false)) break;

    const remaining = Math.max(1, deadlineMs - Date.now());
    await Promise.race([
      editorFrame.first().waitFor({ state: "visible", timeout: remaining }),
      retry.first().waitFor({ state: "visible", timeout: remaining }),
    ]).catch(() => undefined);

    if (await editorFrame.first().isVisible().catch(() => false)) break;

    const shouldRetry = await retry.first().isVisible().catch(() => false);
    if (shouldRetry && retries < 2) {
      retries += 1;
      await retry.first().click();
      continue;
    }
  }

  await expect(editorFrame).toBeVisible({ timeout: 1 });

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
