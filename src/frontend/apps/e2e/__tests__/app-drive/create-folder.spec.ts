import { test } from "./fixtures/scenarios";
import { openWorkspaceFromMyFiles } from "./utils-navigate";
import { createFolderInCurrentFolder } from "./utils-item";
import { expectRowItem } from "./utils-embedded-grid";

test("Create a folder", async ({ page, isolatedWorkspace }) => {
  await page.goto("/");
  await openWorkspaceFromMyFiles(
    page,
    isolatedWorkspace.result.workspace_root.title,
    isolatedWorkspace.result.workspace_root.id,
  );

  const folderName = `My first folder ${isolatedWorkspace.scope.scenario_slug}`;

  await createFolderInCurrentFolder(page, folderName);
  await expectRowItem(page, folderName);
});
