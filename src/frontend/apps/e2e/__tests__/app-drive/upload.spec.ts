import test, { expect, Page, Route } from "@playwright/test";
import { clearDb, login } from "./utils-common";
import path from "path";
import { clickToMyFiles } from "./utils-navigate";

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
  }) => {
    await clearDb();
    await login(page, "drive@example.com");

    // Set limit to 1 KB — well below pv_cm.pdf (~253 KB)
    await mockConfigWithUploadLimit(page, 1024);

    await page.goto("/");
    await clickToMyFiles(page);
    await expect(page.getByText("This tab is empty")).toBeVisible();

    await uploadFile(page, PDF_FILE_PATH);

    // Error toast must appear mentioning the file name and size limit
    await expect(page.getByText('"pv_cm.pdf" is too large')).toBeVisible();

    // The file must not appear in the file list
    await expect(page.getByText("This tab is empty")).toBeVisible();
  });

  test("Uploads a file successfully when it is within DATA_UPLOAD_MAX_MEMORY_SIZE", async ({
    page,
  }) => {
    await clearDb();
    await login(page, "drive@example.com");

    // Set limit to 10 MB — well above pv_cm.pdf (~253 KB)
    await mockConfigWithUploadLimit(page, 10 * 1024 * 1024);

    await page.goto("/");
    await clickToMyFiles(page);
    await expect(page.getByText("This tab is empty")).toBeVisible();

    await uploadFile(page, PDF_FILE_PATH);

    // File should appear in the list and no error toast should be shown
    await expect(page.getByRole("cell", { name: "pv_cm.pdf" })).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText("is too large")).not.toBeVisible();
  });
});
