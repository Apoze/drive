import { test } from "./fixtures/scenarios";
import { createFolderInCurrentFolder } from "./utils-item";
import { createFromTemplate } from "./utils-editor";
import { navigateToFolder, openWorkspaceFromMyFiles } from "./utils-navigate";

test.describe("Create file from template", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("Create a text document (odt)", async ({ page, isolatedWorkspace }) => {
    await openWorkspaceFromMyFiles(page, isolatedWorkspace.result.workspace_root.title);
    await createFromTemplate({
      page,
      templateLabel: /\(ODT\)/,
      filename: `My document ${isolatedWorkspace.scope.scenario_slug}`,
      expectedExtension: "odt",
    });
  });

  test("Create a spreadsheet (ods)", async ({ page, isolatedWorkspace }) => {
    await openWorkspaceFromMyFiles(page, isolatedWorkspace.result.workspace_root.title);
    await createFromTemplate({
      page,
      templateLabel: /\(ODS\)/,
      filename: `My spreadsheet ${isolatedWorkspace.scope.scenario_slug}`,
      expectedExtension: "ods",
    });
  });

  test("Create a presentation (odp)", async ({ page, isolatedWorkspace }) => {
    await openWorkspaceFromMyFiles(page, isolatedWorkspace.result.workspace_root.title);
    await createFromTemplate({
      page,
      templateLabel: /\(ODP\)/,
      filename: `My presentation ${isolatedWorkspace.scope.scenario_slug}`,
      expectedExtension: "odp",
    });
  });
});

test.describe("Create file from template in a folder", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("Create a text document (odt) in a folder", async ({ page, isolatedWorkspace }) => {
    const folderName = `Test folder ${isolatedWorkspace.scope.scenario_slug}`;
    await openWorkspaceFromMyFiles(page, isolatedWorkspace.result.workspace_root.title);
    await createFolderInCurrentFolder(page, folderName);
    await navigateToFolder(
      page,
      folderName,
      ["My files", "My files", isolatedWorkspace.result.workspace_root.title, folderName],
    );
    await createFromTemplate({
      page,
      templateLabel: /\(ODT\)/,
      filename: `My document ${isolatedWorkspace.scope.scenario_slug}`,
      expectedExtension: "odt",
    });
  });

  test("Create a spreadsheet (ods) in a folder", async ({ page, isolatedWorkspace }) => {
    const folderName = `Test folder ${isolatedWorkspace.scope.scenario_slug}`;
    await openWorkspaceFromMyFiles(page, isolatedWorkspace.result.workspace_root.title);
    await createFolderInCurrentFolder(page, folderName);
    await navigateToFolder(
      page,
      folderName,
      ["My files", "My files", isolatedWorkspace.result.workspace_root.title, folderName],
    );
    await createFromTemplate({
      page,
      templateLabel: /\(ODS\)/,
      filename: `My spreadsheet ${isolatedWorkspace.scope.scenario_slug}`,
      expectedExtension: "ods",
    });
  });

  test("Create a presentation (odp) in a folder", async ({ page, isolatedWorkspace }) => {
    const folderName = `Test folder ${isolatedWorkspace.scope.scenario_slug}`;
    await openWorkspaceFromMyFiles(page, isolatedWorkspace.result.workspace_root.title);
    await createFolderInCurrentFolder(page, folderName);
    await navigateToFolder(
      page,
      folderName,
      ["My files", "My files", isolatedWorkspace.result.workspace_root.title, folderName],
    );
    await createFromTemplate({
      page,
      templateLabel: /\(ODP\)/,
      filename: `My presentation ${isolatedWorkspace.scope.scenario_slug}`,
      expectedExtension: "odp",
    });
  });
});
