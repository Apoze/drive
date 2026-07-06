import test, { expect } from "@playwright/test";
import { legacyClearDb, legacyLogin } from "./utils-common";
import { clickToMyFiles } from "./utils-navigate";

const READINESS_CYCLES = 3;

test("E2E runner readiness smoke matches the app-drive preamble", async ({ page }) => {
  test.skip(
    process.env.E2E_READYNESS_SMOKE !== "1" || test.info().project.name !== "chromium",
    "Readiness smoke is only used by the Chromium from-scratch bootstrap.",
  );

  for (let cycle = 0; cycle < READINESS_CYCLES; cycle += 1) {
    await legacyClearDb(page);
    await legacyLogin(page, "drive@example.com");
    await page.goto("/");
    await clickToMyFiles(page);

    await expect(page).toHaveURL(/\/explorer\/items\/my-files/, {
      timeout: 20_000,
    });
    await expect(page.getByTestId("default-route-button")).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page
        .getByRole("columnheader", { name: /^Name\b/i })
        .or(page.getByRole("cell", { name: /^Name$/i }))
        .first(),
    ).toBeVisible({ timeout: 20_000 });
  }
});
