import { expect, test } from "@playwright/test";
import {
  dismissReleaseNotesIfPresent,
  keyCloakSignIn,
} from "./utils-common";
import { expectExplorerShellReady } from "./utils-explorer";
import { getRowItem } from "./utils-embedded-grid";
import { createFolderInCurrentFolder } from "./utils-item";

test.setTimeout(90_000);

test("Long desktop breadcrumbs stay readable on LAN without a horizontal scrollbar", async ({
  page,
}) => {
  const stamp = Date.now();
  const folderNames = [
    `Desktop breadcrumb parent ${stamp}`,
    `Desktop breadcrumb archive ${stamp}`,
    `Desktop breadcrumb evidence ${stamp}`,
    `Desktop breadcrumb final node ${stamp}`,
  ];

  await page.goto("/");
  await keyCloakSignIn(page, "drive", "drive");
  await dismissReleaseNotesIfPresent(page, 10_000);

  await page.goto("/explorer/items/my-files");
  await expectExplorerShellReady(page);

  for (const folderName of folderNames) {
    await createFolderInCurrentFolder(page, folderName);
    const row = await getRowItem(page, folderName);
    await row.dblclick();
    await expectExplorerShellReady(page);
  }

  const breadcrumbs = page.getByTestId("explorer-breadcrumbs");
  await expect(breadcrumbs).toBeVisible({ timeout: 20_000 });

  const metrics = await breadcrumbs.evaluate((element) => {
    const htmlElement = element as HTMLElement;
    const style = window.getComputedStyle(htmlElement);
    return {
      clientWidth: htmlElement.clientWidth,
      itemCount: htmlElement.querySelectorAll(".c__breadcrumbs__item").length,
      overflowX: style.overflowX,
      scrollWidth: htmlElement.scrollWidth,
    };
  });

  expect(metrics.itemCount).toBeGreaterThanOrEqual(folderNames.length);
  expect(metrics.overflowX).not.toBe("auto");
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1);
});
