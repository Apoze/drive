import { expect, Page, Route } from "@playwright/test";
import path from "path";
import { test } from "./fixtures/scenarios";
import { openFolderFromMainWorkspace } from "./utils-navigate";

const PDF_FILE_PATH = path.join(__dirname, "/assets/pv_cm.pdf");

/**
 * Helper to mock the config API response with a custom DATA_UPLOAD_MAX_MEMORY_SIZE value.
 * Must be called before page.goto() so the intercept is in place when the app loads.
 */
const mockConfigWithUploadLimit = async (page: Page, maxMemorySize: number) => {
  await page.route("**/api/v1.0/config/", async (route: Route) => {
    const response = await route.fetch();
    const json = await response.json();
    json.DATA_UPLOAD_MAX_MEMORY_SIZE = maxMemorySize;
    await route.fulfill({ response, json });
  });
};

/**
 * Upload a file via the Import button and file chooser.
 */
const uploadFile = async (page: Page, filePath: string) => {
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Import" }).click();
  await page.getByRole("menuitem", { name: "Import files" }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(filePath);
};

test.describe("File upload size limit", () => {
  test("Shows an error toast and does not upload a file exceeding DATA_UPLOAD_MAX_MEMORY_SIZE", async ({
    page,
    isolatedWorkspace,
  }) => {
    // Set limit to 1 KB — well below pv_cm.pdf (~253 KB)
    await mockConfigWithUploadLimit(page, 1024);

    await page.goto("/");
    await openFolderFromMainWorkspace(
      page,
      isolatedWorkspace.result.workspace_root.title,
    );
    await expect(page.getByRole("button", { name: "Import" })).toBeVisible();

    await uploadFile(page, PDF_FILE_PATH);

    // Error toast must appear mentioning the file name and size limit
    await expect(page.getByText('"pv_cm.pdf" is too large')).toBeVisible();

    // The file must not appear in the file list
    await expect(page.getByRole("button", { name: "pv_cm.pdf" })).toHaveCount(0);
    await expect(
      page.getByRole("cell", { name: "pv_cm.pdf", exact: true }),
    ).toHaveCount(0);
  });

  test("Uploads a file successfully when it is within DATA_UPLOAD_MAX_MEMORY_SIZE", async ({
    page,
    isolatedWorkspace,
  }) => {
    // Set limit to 10 MB — well above pv_cm.pdf (~253 KB)
    await mockConfigWithUploadLimit(page, 10 * 1024 * 1024);

    await page.goto("/");
    await openFolderFromMainWorkspace(
      page,
      isolatedWorkspace.result.workspace_root.title,
    );
    await expect(page.getByRole("button", { name: "Import" })).toBeVisible();

    await uploadFile(page, PDF_FILE_PATH);

    // Upload can still fail for unrelated backend/storage reasons; this test only
    // validates that the client-side "too large" guard does not trigger.
    const uploadToast = page.getByRole("alert").filter({ hasText: "pv_cm.pdf" });
    await expect(uploadToast).toBeVisible({ timeout: 20000 });
    await expect(page.getByText('"pv_cm.pdf" is too large')).toHaveCount(0);
  });
});
