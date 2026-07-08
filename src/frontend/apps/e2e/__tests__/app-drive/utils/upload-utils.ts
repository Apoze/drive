import { expect, Locator, Page, Route } from "@playwright/test";

export const uploadFile = async (page: Page, filePath: string | string[]) => {
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Import" }).click();
  await page.getByRole("menuitem", { name: "Import files" }).click();

  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(filePath);
};

export const mockConfigWithUploadLimit = async (
  page: Page,
  maxMemorySize: number,
) => {
  await page.route("**/api/v1.0/config/", async (route: Route) => {
    const response = await route.fetch();
    const json = await response.json();
    json.DATA_UPLOAD_MAX_MEMORY_SIZE = maxMemorySize;
    await route.fulfill({ response, json });
  });
};

export const getUploadToast = (page: Page): Locator =>
  page.locator(".file-upload-toast").last();

export const getFileRow = (page: Page, fileName: string): Locator =>
  getUploadToast(page)
    .locator(".file-upload-toast__files__item")
    .filter({ hasText: fileName });

export const getFileRowCheckIcon = (page: Page, fileName: string): Locator =>
  getFileRow(page, fileName).locator(
    ".file-upload-toast__files__item__check",
  );

export const getToastCloseButton = (page: Page): Locator =>
  getUploadToast(page)
    .locator(".file-upload-toast__description")
    .getByRole("button")
    .filter({ has: page.locator("span.material-icons", { hasText: "close" }) })
    .last();

export const getUploadProgressArea = (
  page: Page,
  fileName: string,
): Locator =>
  getFileRow(page, fileName).locator(
    ".file-upload-toast__files__item__progress--hoverable",
  );

export const mockSlowUpload = async (
  page: Page,
): Promise<{ resolve: () => void }> => {
  let resolveUpload: (() => void) | undefined;
  const uploadPromise = new Promise<void>((resolve) => {
    resolveUpload = resolve;
  });

  await page.route("**/*", async (route) => {
    const request = route.request();
    const isObjectStoragePut =
      request.method() === "PUT" &&
      !request.url().includes("/api/v1.0/") &&
      /9000|s3|minio|seaweed/i.test(request.url());

    if (!isObjectStoragePut) {
      await route.continue();
      return;
    }

    await uploadPromise;
    await route.continue().catch(() => undefined);
  });

  return {
    resolve: () => resolveUpload?.(),
  };
};

export const mockSlowUploadEnded = async (
  page: Page,
): Promise<{ resolve: () => void }> => {
  let resolveUploadEnded: (() => void) | undefined;
  const uploadEndedPromise = new Promise<void>((resolve) => {
    resolveUploadEnded = resolve;
  });

  await page.route("**/api/v1.0/items/*/upload-ended/", async (route) => {
    await uploadEndedPromise;
    await route.continue().catch(() => undefined);
  });

  return {
    resolve: () => resolveUploadEnded?.(),
  };
};

export const expectUploadCancelled = async (page: Page, fileName: string) => {
  await expect(getFileRow(page, fileName)).not.toBeVisible({ timeout: 10_000 });
};
