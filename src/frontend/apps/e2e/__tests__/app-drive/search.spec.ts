import { expect, type Page } from "@playwright/test";

import { test } from "./fixtures/scenarios";
import { dismissReleaseNotesIfPresent } from "./utils-common";
import { expectExplorerBreadcrumbs } from "./utils-explorer";
import { clickToMyFiles, getMainWorkspaceBreadcrumbs } from "./utils-navigate";
import { waitForExplorerGridToSettle } from "./utils-embedded-grid";

const openSearch = async (page: Page) => {
  await waitForExplorerGridToSettle(page);
  await page.getByRole("button", { name: "Search" }).click();
  const input = page.getByRole("combobox", { name: "Quick search input" });
  await expect(input).toBeVisible();
  return input;
};

const refillSearchInput = async (
  input: ReturnType<Page["getByRole"]>,
  query: string,
) => {
  await input.fill("");
  await input.pressSequentially(query);
};

const fillSearchAndExpect = async (
  input: ReturnType<Page["getByRole"]>,
  query: string,
  assertion: () => Promise<void>,
) => {
  try {
    await input.fill(query);
    await assertion();
  } catch {
    await refillSearchInput(input, query);
    await assertion();
  }
};

const fillSearchInputWithRetry = async (
  input: ReturnType<Page["getByRole"]>,
  query: string,
) => {
  try {
    await input.fill(query);
  } catch {
    await refillSearchInput(input, query);
  }
};

test.beforeEach(async ({ page, searchDataset }) => {
  void searchDataset;
  await page.goto("/");
  await dismissReleaseNotesIfPresent(page, 5_000);
});

test("Search somes items and shows them in the search modal", async ({
  page,
  searchDataset,
}) => {
  const input = await openSearch(page);
  const datasetRootTitle = searchDataset.result.dataset_root.title;

  let searchItems = page.getByTestId("search-item");
  await expect(searchItems).toHaveCount(0);

  await fillSearchAndExpect(input, "meeting", async () => {
    await expect(page.getByTestId("search-item")).toHaveCount(3, {
      timeout: 15_000,
    });
  });

  searchItems = page.getByTestId("search-item");

  let searchItem = page.getByRole("option", { name: /^Meetings\b/i });
  await expect(searchItem).toContainText(
    `My workspace / ${datasetRootTitle} / Dev Team`,
  );

  searchItem = page.getByRole("option", {
    name: "Meeting notes 5th September",
  });
  await expect(searchItem).toContainText(
    `My workspace / ${datasetRootTitle} / Dev Team / Meetings`,
  );

  searchItem = page.getByRole("option", {
    name: "Meeting notes 15th September",
  });
  await expect(searchItem).toContainText(
    `My workspace / ${datasetRootTitle} / Dev Team / Meetings`,
  );

  await fillSearchAndExpect(input, "sale", async () => {
    await expect(page.getByTestId("search-item")).toHaveCount(1, {
      timeout: 15_000,
    });
  });

  searchItems = page.getByTestId("search-item");

  searchItem = page.getByRole("option", {
    name: "Sales report",
  });
  await expect(searchItem).toContainText(
    `My workspace / ${datasetRootTitle} / Project 2025`,
  );
});

test("Search folder and click on it", async ({ page, searchDataset }) => {
  await clickToMyFiles(page);

  const input = await openSearch(page);
  await fillSearchAndExpect(input, "meetings", async () => {
    await expect(page.getByRole("option", { name: "Meetings" })).toBeVisible({
      timeout: 15_000,
    });
  });

  const button = page.getByRole("option", { name: "Meetings" });
  await button.click();

  await expectExplorerBreadcrumbs(
    page,
    getMainWorkspaceBreadcrumbs(
      searchDataset.result.dataset_root.title,
      "Dev Team",
      "Meetings",
    ),
  );
});

test("Search file and click on it", async ({ page }) => {
  await clickToMyFiles(page);
  const input = await openSearch(page);
  await fillSearchAndExpect(input, "budget", async () => {
    await expect(page.getByRole("option", { name: "Budget report" })).toBeVisible({
      timeout: 15_000,
    });
  });

  const button = page.getByRole("option", { name: "Budget report" });
  await button.click();

  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible();
  await expect(filePreview.getByText("Budget report")).toBeVisible();
});

test("Search folder from trash and cannot navigate to it", async ({ page }) => {
  await clickToMyFiles(page);

  await openSearch(page);

  let searchItems = page.getByTestId("search-item");
  await expect(searchItems).toHaveCount(0);

  const input = page.getByRole("combobox", { name: "Quick search input" });
  await fillSearchInputWithRetry(input, "I am");

  await page.getByRole("button", { name: "Location" }).click();
  await page.getByRole("option", { name: "Recycle bin" }).click();

  await fillSearchAndExpect(input, "I am", async () => {
    await expect(page.getByTestId("search-item")).toHaveCount(1, {
      timeout: 15_000,
    });
  });

  const button = page.getByRole("option", { name: "I am deleted" });
  await button.click();

  await expect(page.getByText("This folder is in the trash")).toBeVisible();
  await expect(
    page.getByText("To display this folder, you need to restore it first"),
  ).toBeVisible();

  await page.getByRole("button", { name: "Ok" }).click();

  await expect(page.getByText("This folder is in the trash")).not.toBeVisible();
  await expect(
    page.getByText("To display this folder, you need to restore it first"),
  ).not.toBeVisible();
});

test("Search a deleted file and click on it", async ({ page }) => {
  await clickToMyFiles(page);
  const input = await openSearch(page);
  await fillSearchInputWithRetry(input, "resum");

  await page.getByRole("button", { name: "Location" }).click();
  await page.getByRole("option", { name: "Recycle bin" }).click();

  await fillSearchAndExpect(input, "resum", async () => {
    await expect(page.getByTestId("search-item")).toHaveCount(1, {
      timeout: 15_000,
    });
  });

  const button = page.getByRole("option", { name: "Resume" });
  await button.click();

  const filePreview = page.getByTestId("file-preview");
  await expect(filePreview).toBeVisible();
  await expect(filePreview.getByText("Resume")).toBeVisible();
});
