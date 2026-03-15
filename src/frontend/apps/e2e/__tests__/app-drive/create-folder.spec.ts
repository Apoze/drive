import { test } from "./fixtures/scenarios";
import { navigateToFolder, openMainWorkspaceFromMyFiles } from "./utils-navigate";
import { createFolderInCurrentFolder } from "./utils-item";
import { expectRowItem } from "./utils-embedded-grid";

test("Create a folder", async ({ page, isolatedWorkspace }) => {
  await page.goto("/");
  await openMainWorkspaceFromMyFiles(page);
  await navigateToFolder(page, isolatedWorkspace.result.workspace_root.title, [
    "My files",
    "My files",
    isolatedWorkspace.result.workspace_root.title,
  ]);

  const folderName = `My first folder ${isolatedWorkspace.scope.scenario_slug}`;

  await createFolderInCurrentFolder(page, folderName);
  await expectRowItem(page, folderName);
});
