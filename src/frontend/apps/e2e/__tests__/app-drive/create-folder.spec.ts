import test from "@playwright/test";
import { clearDb, login } from "./utils-common";
import { openMainWorkspaceFromMyFiles } from "./utils-navigate";
import { createFolderInCurrentFolder } from "./utils-item";
import { expectRowItem } from "./utils-embedded-grid";

test("Create a folder", async ({ page }, testInfo) => {
  await clearDb();
  await login(page, "drive@example.com");

  await page.goto("/");
  await openMainWorkspaceFromMyFiles(page);

  const stamp = `${testInfo.workerIndex}_${Date.now()}`;
  const folderName = `My first folder ${stamp}`;

  await createFolderInCurrentFolder(page, folderName);
  await expectRowItem(page, folderName);
});
