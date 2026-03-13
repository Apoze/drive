import test, { expect, type Page } from "@playwright/test";
import { clearDb, login } from "./utils-common";
import { createFolderInCurrentFolder } from "./utils-item";
import { navigateToFolder, openMainWorkspaceFromMyFiles } from "./utils-navigate";

const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const openCreateMenu = async (page: Page) => {
  const createButton = page.getByRole("button", {
    // The left sidebar create dropdown button includes the leading icon text ("add").
    name: /^add\s+(Create|New|Créer|Creëeren)$/i,
  });
  await expect(createButton).toBeVisible({ timeout: 20_000 });
  await createButton.click();
};

const createFromTemplate = async (
  page: Page,
  templateLabel: RegExp,
  filename: string,
  expectedExtension: string,
) => {
  await openCreateMenu(page);

  const menuItem = page.getByRole("menuitem", { name: templateLabel });
  await expect(menuItem).toBeVisible({ timeout: 20_000 });
  await menuItem.click();

  const filenameInputSelector = "input.explorer__create-file__modal__filename-input";
  const filenameInput = page.locator(filenameInputSelector);
  const dialog = page.getByRole("dialog").filter({ has: filenameInput });

  await expect(dialog).toBeVisible({ timeout: 20_000 });
  await expect(filenameInput).toBeVisible({ timeout: 20_000 });
  await filenameInput.fill(filename);

  await dialog
    .getByRole("button", { name: /^(Create|Créer|Maken)$/i })
    .click();
  await expect(dialog).toBeHidden({ timeout: 20_000 });

  const expectedFilename = new RegExp(
    `^${escapeRegExp(filename)}.*\\.${escapeRegExp(expectedExtension)}$`,
  );
  await expect(
    page.getByRole("heading", { name: expectedFilename }),
  ).toBeVisible({ timeout: 20_000 });
};

test.describe("Create file from template", () => {
  test.beforeEach(async ({ page }) => {
    await clearDb(page);
    await login(page, "drive@example.com");
    await page.goto("/");
  });

  test("Create a text document (odt)", async ({ page }) => {
    await createFromTemplate(page, /\(ODT\)/, "My document", "odt");
  });

  test("Create a spreadsheet (ods)", async ({ page }) => {
    await createFromTemplate(page, /\(ODS\)/, "My spreadsheet", "ods");
  });

  test("Create a presentation (odp)", async ({ page }) => {
    await createFromTemplate(page, /\(ODP\)/, "My presentation", "odp");
  });
});

test.describe("Create file from template in a folder", () => {
  test.beforeEach(async ({ page }) => {
    await clearDb(page);
    await login(page, "drive@example.com");
    await page.goto("/");
    await openMainWorkspaceFromMyFiles(page);
    await createFolderInCurrentFolder(page, "Test folder");
    await navigateToFolder(page, "Test folder", [
      "My files",
      "My files",
      "Test folder",
    ]);
  });

  test("Create a text document (odt) in a folder", async ({ page }) => {
    await createFromTemplate(page, /\(ODT\)/, "My document", "odt");
  });

  test("Create a spreadsheet (ods) in a folder", async ({ page }) => {
    await createFromTemplate(page, /\(ODS\)/, "My spreadsheet", "ods");
  });

  test("Create a presentation (odp) in a folder", async ({ page }) => {
    await createFromTemplate(page, /\(ODP\)/, "My presentation", "odp");
  });
});
