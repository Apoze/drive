import { expect } from "@playwright/test";
import { test } from "../fixtures/scenarios";
import { clickOnRowItemActions, getRowItem } from "../utils-embedded-grid";
import { openFolderFromMainWorkspace } from "../utils-navigate";
import { createFolderInCurrentFolder } from "../utils-item";

test.describe("Right content info", () => {
  test.beforeEach(async ({ page, isolatedWorkspace }) => {
    await page.goto("/");
    await openFolderFromMainWorkspace(
      page,
      isolatedWorkspace.result.workspace_root.title,
    );
  });

  test("Check that the right content is displayed correctly", async ({
    page,
    isolatedWorkspace,
  }) => {
    const folderName = `testFolder-${isolatedWorkspace.scope.scenario_slug}`;
    await createFolderInCurrentFolder(page, folderName);
    await getRowItem(page, folderName);
    await clickOnRowItemActions(page, folderName, "Info");
    const rightPanel = page.getByTestId("right-panel");
    await expect(rightPanel).toBeVisible();
    await expect(
      rightPanel.getByText(folderName, { exact: true }),
    ).toBeVisible();
  });

  test("Right panel updates item name after rename", async ({
    page,
    isolatedWorkspace,
  }) => {
    const originalName = `OriginalName-${isolatedWorkspace.scope.scenario_slug}`;
    const updatedName = `UpdatedName-${isolatedWorkspace.scope.scenario_slug}`;

    await createFolderInCurrentFolder(page, originalName);
    await clickOnRowItemActions(page, originalName, "Info");

    const rightPanel = page.getByTestId("right-panel");
    await expect(rightPanel).toBeVisible();
    await expect(
      rightPanel.getByText(originalName, { exact: true }),
    ).toBeVisible();

    await clickOnRowItemActions(page, originalName, "Rename");
    await page.getByRole("textbox", { name: "New name" }).fill(updatedName);
    await page.getByRole("button", { name: "Rename" }).click();

    await expect(
      rightPanel.getByText(updatedName, { exact: true }),
    ).toBeVisible();
    await expect(
      rightPanel.getByText(originalName, { exact: true }),
    ).not.toBeVisible();
  });

  test("Activity opens lazily and shows a real item event", async ({
    page,
    isolatedWorkspace,
  }) => {
    const folderName = `Activity-${isolatedWorkspace.scope.scenario_slug}`;
    await createFolderInCurrentFolder(page, folderName);
    await clickOnRowItemActions(page, folderName, "Info");

    const rightPanel = page.getByTestId("right-panel");
    const activityButton = rightPanel.getByRole("button", {
      name: /^(Activity|Activité|Activiteit)$/i,
    });
    await expect(activityButton).toHaveAttribute("aria-expanded", "false");
    await activityButton.click();

    await expect(activityButton).toHaveAttribute("aria-expanded", "true");
    await expect(
      rightPanel.getByText(
        /created this item|a créé cet élément|heeft dit item aangemaakt/i,
      ),
    ).toBeVisible();
    await expect(rightPanel.locator("time[datetime]").first()).toHaveAttribute(
      "aria-label",
      /.+/,
    );
  });
});
