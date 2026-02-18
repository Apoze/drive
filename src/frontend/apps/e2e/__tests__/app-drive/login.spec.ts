import { expect, test as setup } from "@playwright/test";

import { dismissReleaseNotesIfPresent, keyCloakSignIn } from "./utils-common";

setup("authenticate as drive", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  await page.content();

  await keyCloakSignIn(page, "drive", "drive");
  await dismissReleaseNotesIfPresent(page, 10_000);

  await expect(page).toHaveURL(/\/explorer\//, { timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Import" })).toBeVisible({
    timeout: 20_000,
  });
});
