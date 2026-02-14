import test, { expect, Page } from "@playwright/test";
import { clearDb, login } from "./utils-common";

const openCreateFileModal = async (page: Page) => {
  await page.getByRole("button", { name: "Create" }).first().click();
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

  const loading = filePreview.getByText("Loading document...");
  await expect(loading).toBeVisible({ timeout: 20000 });
  await expect(loading).toBeHidden({ timeout: 5000 });

  const firstOpenMs = Date.now() - start;
  console.log(`wopi_onlyoffice_first_open_ms file=${expectedFilename} ms=${firstOpenMs}`);

  // Close preview
  await filePreview.getByRole("button", { name: "close" }).click();
  await expect(filePreview).toBeHidden({ timeout: 10000 });

  // Re-open (existing file)
  const reopenStart = Date.now();
  await page.getByRole("cell", { name: expectedFilename, exact: true }).click();
  const filePreview2 = page.getByTestId("file-preview");
  await expect(filePreview2).toBeVisible({ timeout: 20000 });
  await expect(filePreview2.getByText("Loading document...")).toBeHidden({
    timeout: 5000,
  });

  const reopenMs = Date.now() - reopenStart;
  console.log(`wopi_onlyoffice_reopen_ms file=${expectedFilename} ms=${reopenMs}`);

  await filePreview2.getByRole("button", { name: "close" }).click();
  await expect(filePreview2).toBeHidden({ timeout: 10000 });
};

test.setTimeout(2 * 60 * 1000);

test("ONLYOFFICE editnew: new OOXML loads fast", async ({ page }) => {
  await clearDb();
  await login(page, "drive@example.com");

  await page.goto("/");

  await createAndWaitWopi({
    page,
    stem: "onlyoffice-editnew-docx",
    kindLabel: "Text document",
    extensionLabelRegex: /Word \\(OOXML\\)/,
    expectedFilename: "onlyoffice-editnew-docx.docx",
  });

  await createAndWaitWopi({
    page,
    stem: "onlyoffice-editnew-xlsx",
    kindLabel: "Spreadsheet",
    extensionLabelRegex: /Excel \\(OOXML\\)/,
    expectedFilename: "onlyoffice-editnew-xlsx.xlsx",
  });

  await createAndWaitWopi({
    page,
    stem: "onlyoffice-editnew-pptx",
    kindLabel: "Presentation",
    extensionLabelRegex: /PowerPoint \\(OOXML\\)/,
    expectedFilename: "onlyoffice-editnew-pptx.pptx",
  });
});

