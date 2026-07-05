import { expect } from "@playwright/test";
import { test } from "./fixtures/auth";
import { ensureBootstrappedActorSession } from "./utils-common";
import { expectExplorerRouteReady } from "./utils-explorer";
import { createFolderInCurrentFolder } from "./utils-item";
import { getRowItem } from "./utils-embedded-grid";
import { clickToMyFiles } from "./utils-navigate";

test.setTimeout(90_000);
test.use({ authActorEmail: "drive@example.com" });

test("Redirects to /401 when session cookies are cleared then re-login and get redirected to the folder", async ({
  page,
  context,
  authActor,
}) => {
  await page.goto("/");
  await clickToMyFiles(page);

  const folderName = `Secret folder ${authActor.scope.actor_slug}`;
  await createFolderInCurrentFolder(page, folderName);
  const folderItem = await getRowItem(page, folderName);
  await folderItem.dblclick();
  await page.waitForURL(/\/explorer\/items\/[0-9a-f-]{36}/, { timeout: 20_000 });
  const folderUrl = page.url();

  await context.clearCookies();

  await page.reload();

  await expect(page).toHaveURL(/.*\/401/, { timeout: 10000 });
  await expect(
    page.getByText("You need to be logged in to access the documents."),
  ).toBeVisible();

  await expect(
    page
      .locator(".drive__generic-disclaimer")
      .getByRole("button", { name: "Login" }),
  ).toBeVisible();

  await ensureBootstrappedActorSession(page, authActor);
  await page.goto(folderUrl);

  await expectExplorerRouteReady(page, new URL(folderUrl).pathname);
});
