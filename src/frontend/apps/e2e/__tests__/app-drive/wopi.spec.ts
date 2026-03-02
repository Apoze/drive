import test, { expect, Page } from "@playwright/test";
import { clearDb, login } from "./utils-common";
import { openMainWorkspaceFromMyFiles } from "./utils-navigate";
import { grantClipboardPermissions } from "./utils/various-utils";

const openCreateFileModal = async (page: Page) => {
  await page.getByRole("button", { name: "Create" }).first().click({ force: true });
  await page.getByRole("menuitem", { name: "More formats..." }).click();
  const dialog = page.getByRole("dialog", { name: "Create a new file" });
  await expect(dialog).toBeVisible();
  return dialog;
};

test("Wopi editor", async ({ page, context, browserName }) => {
  test.skip(browserName !== "chromium", "Only runs on chromium");
  test.setTimeout(120_000);
  await grantClipboardPermissions(browserName, context);
  await clearDb();
  await login(page, "drive@example.com");
  await page.goto("/");
  await openMainWorkspaceFromMyFiles(page);

  const stamp = `${Date.now()}`;
  const dialog = await openCreateFileModal(page);
  await dialog.locator(".explorer__create-file__modal__filename-input").fill(`wopi-odt-${stamp}`);
  await dialog.getByRole("button", { name: "Text document" }).click();
  await dialog.getByRole("button", { name: /\.odt\b/i }).click();
  await dialog.getByRole("button", { name: "Create" }).click();

  // Check that the file preview is visible
  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible({ timeout: 20_000 });

  // "Loading document..." is optional; wait for the iframe either way.
  const loading = filePreview.getByText("Loading document...");
  const loadingWasVisible = await loading.isVisible().catch(() => false);
  if (loadingWasVisible) {
    await expect(loading).toBeHidden({ timeout: 60_000 });
  }

  const wopiIframe = filePreview.locator('iframe[name="office_frame"]');
  await expect(wopiIframe).toBeVisible({ timeout: 60_000 });

  const loadingEditor = filePreview.getByText("Loading document...");
  const retry = filePreview
    .getByRole("link", { name: /retry/i })
    .or(filePreview.getByRole("button", { name: /retry/i }));

  // WOPI editors (ONLYOFFICE/Collabora) can occasionally fail to load and show a Retry
  // action instead of the editor. Avoid flakiness via bounded retries (no sleeps).
  const deadlineMs = Date.now() + 90_000;
  let retries = 0;
  while (Date.now() < deadlineMs) {
    const loadingWasVisible = await loadingEditor.isVisible().catch(() => false);
    if (loadingWasVisible) {
      const remaining = Math.max(1, deadlineMs - Date.now());
      await expect(loadingEditor).toBeHidden({ timeout: remaining }).catch(() => undefined);
    }

    // If the iframe is visible and there is no loading overlay, assume the editor loaded.
    const retryVisible = await retry.first().isVisible().catch(() => false);
    const loadingVisible = await loadingEditor.isVisible().catch(() => false);
    if (!retryVisible && !loadingVisible) break;

    const remaining = Math.max(1, deadlineMs - Date.now());
    await Promise.race([
      retry.first().waitFor({ state: "visible", timeout: remaining }),
    ]).catch(() => undefined);

    const shouldRetry = await retry.first().isVisible().catch(() => false);
    if (shouldRetry && retries < 2) {
      retries += 1;
      await retry.first().click();
      continue;
    }
  }

  // After retries/bounded wait, the editor must not be stuck on the loading overlay.
  const loadingStillVisible = await loadingEditor.isVisible().catch(() => false);
  if (loadingStillVisible) {
    await expect(loadingEditor).toBeHidden({ timeout: 1 });
  }

  // Close preview
  await filePreview.getByRole("button", { name: "close" }).click();
  await expect(filePreview).toBeHidden({ timeout: 10_000 });
});
