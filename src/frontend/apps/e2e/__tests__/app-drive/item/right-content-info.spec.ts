import { expect } from "@playwright/test";
import { test } from "../fixtures/scenarios";
import { clickOnRowItemActions, getRowItem } from "../utils-embedded-grid";
import { openFolderFromMainWorkspace } from "../utils-navigate";
import { createFolderInCurrentFolder } from "../utils-item";

test("Check that the right content is displayed correctly", async ({
  page,
  isolatedWorkspace,
}) => {
  await page.goto("/");
  await openFolderFromMainWorkspace(
    page,
    isolatedWorkspace.result.workspace_root.title,
  );
  await createFolderInCurrentFolder(page, "testFolder");
  await getRowItem(page, "testFolder");
  await clickOnRowItemActions(page, "testFolder", "Info");
  const rightPanel = page.getByTestId("right-panel");
  await expect(rightPanel).toBeVisible();
  await expect(rightPanel.getByText("testFolder")).toBeVisible();
});
