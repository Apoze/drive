import test, { expect } from "@playwright/test";
import { clearDb, keyCloakSignIn, login } from "./utils-common";
import { createFolderInCurrentFolder } from "./utils-item";
import { getRowItem } from "./utils-embedded-grid";
import { clickToMyFiles } from "./utils-navigate";

test.setTimeout(90_000);

test("Redirects to /401 when session cookies are cleared then re-login and get redirected to the folder", async ({
  page,
  context,
}) => {
  await clearDb();
  await login(page, "drive@example.com");
  await page.goto("/");
  await clickToMyFiles(page);

  await createFolderInCurrentFolder(page, "Secret folder");
  const folderItem = await getRowItem(page, "Secret folder");
  await folderItem.dblclick();
  await page.waitForURL(/\/explorer\/items\/[0-9a-f-]{36}/, { timeout: 20_000 });
  const folderUrl = page.url();

  await context.clearCookies();

  await page.reload();

  await expect(page).toHaveURL(/.*\/401/, { timeout: 10000 });
  await expect(
    page.getByText("You need to be logged in to access the documents."),
  ).toBeVisible();

  await page
    .locator(".drive__generic-disclaimer")
    .getByRole("button", { name: "Login" })
    .click();

  await keyCloakSignIn(page, "drive", "drive", false);

  await expect(page).toHaveURL(folderUrl);
});
