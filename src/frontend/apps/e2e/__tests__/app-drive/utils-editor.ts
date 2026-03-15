import { expect, type Locator, type Page } from "@playwright/test";

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export const openCreateMenu = async (page: Page) => {
  const createButton = page.getByRole("button", {
    name: /^add\s+(Create|New|Créer|Creëeren)$/i,
  });
  await expect(createButton).toBeVisible({ timeout: 20_000 });
  await createButton.click();
};

export const openCreateFileModal = async (page: Page) => {
  await openCreateMenu(page);
  await page.getByRole("menuitem", { name: "More formats..." }).click();
  const dialog = page.getByRole("dialog", { name: "Create a new file" });
  await expect(dialog).toBeVisible({ timeout: 20_000 });
  return dialog;
};

export const waitForEditorFrame = async ({
  filePreview,
  iframe,
  timeoutMs = 60_000,
  maxRetries = 2,
}: {
  filePreview: Locator;
  iframe: Locator;
  timeoutMs?: number;
  maxRetries?: number;
}) => {
  const loading = filePreview.getByText("Loading document...");
  const retry = filePreview
    .getByRole("link", { name: /retry/i })
    .or(filePreview.getByRole("button", { name: /retry/i }));

  const loadingWasVisible = await loading.isVisible().catch(() => false);
  if (loadingWasVisible) {
    await expect(loading).toBeHidden({ timeout: timeoutMs }).catch(() => undefined);
  }

  const deadlineMs = Date.now() + timeoutMs;
  let retries = 0;

  while (Date.now() < deadlineMs) {
    if (await iframe.first().isVisible().catch(() => false)) {
      return;
    }

    const remaining = Math.max(1, deadlineMs - Date.now());
    await Promise.race([
      iframe.first().waitFor({ state: "visible", timeout: remaining }),
      retry.first().waitFor({ state: "visible", timeout: remaining }),
    ]).catch(() => undefined);

    if (await iframe.first().isVisible().catch(() => false)) {
      return;
    }

    const shouldRetry = await retry.first().isVisible().catch(() => false);
    if (shouldRetry && retries < maxRetries) {
      retries += 1;
      await retry.first().click();
      continue;
    }
  }

  await expect(iframe.first()).toBeVisible({ timeout: 1 });
};

export const createEditorFileFromMoreFormats = async ({
  page,
  stem,
  kindLabel,
  extensionLabelRegex,
}: {
  page: Page;
  stem: string;
  kindLabel: "Text document" | "Spreadsheet" | "Presentation";
  extensionLabelRegex: RegExp;
}) => {
  const dialog = await openCreateFileModal(page);
  await dialog.locator(".explorer__create-file__modal__filename-input").fill(stem);
  await dialog.getByRole("button", { name: kindLabel }).click();
  await dialog.getByRole("button", { name: extensionLabelRegex }).click();
  await dialog.getByRole("button", { name: "Create" }).click();

  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible({ timeout: 20_000 });
  return filePreview;
};

export const createFromTemplate = async ({
  page,
  templateLabel,
  filename,
  expectedExtension,
}: {
  page: Page;
  templateLabel: RegExp;
  filename: string;
  expectedExtension: string;
}) => {
  await openCreateMenu(page);

  const menuItem = page.getByRole("menuitem", { name: templateLabel });
  await expect(menuItem).toBeVisible({ timeout: 20_000 });
  await menuItem.click();

  const filenameInputSelector = "input.explorer__create-file__modal__filename-input";
  const filenameInput = page.locator(filenameInputSelector);
  const dialog = page.getByRole("dialog").filter({ has: filenameInput });

  await expect(dialog).toBeVisible({ timeout: 20_000 });
  await filenameInput.fill(filename);
  await dialog.getByRole("button", { name: /^(Create|Créer|Maken)$/i }).click();
  await expect(dialog).toBeHidden({ timeout: 20_000 });

  const expectedFilename = new RegExp(
    `^${escapeRegExp(filename)}.*\\.${escapeRegExp(expectedExtension)}$`,
  );
  await expect(
    page.getByRole("heading", { name: expectedFilename }),
  ).toBeVisible({ timeout: 20_000 });
};

export const closeFilePreview = async (page: Page) => {
  const filePreview = page.getByTestId("file-preview");
  await filePreview.getByRole("button", { name: "close" }).click();
  await expect(filePreview).toBeHidden({ timeout: 10_000 });
};
