import { Page, expect } from "@playwright/test";
import { getItemTree, openTreeNode } from "../utils-tree";
import {
  clearExplorerSelectionIfPresent,
  expectRowItem,
  expectRowItemIsNotVisible,
  getRowItem,
} from "../utils-embedded-grid";
import { clickToFavorites } from "../utils-navigate";

const waitForFavoriteMutation = async (
  page: Page,
  method: "POST" | "DELETE",
) => {
  await page
    .waitForResponse(
      (response) => {
        const request = response.request();
        return (
          request.method() === method &&
          response.url().includes("/api/v1.0/items/") &&
          response.url().includes("/favorite/") &&
          response.status() >= 200 &&
          response.status() < 300
        );
      },
      { timeout: 20_000 },
    )
    .catch(() => undefined);
};

const clickFavoriteContextMenuAction = async (
  page: Page,
  itemName: string,
  actionName: RegExp,
) => {
  const row = await getRowItem(page, itemName);
  await row.click({ button: "right" });
  const action = page.getByRole("menuitem", { name: actionName }).first();
  await expect(action).toBeVisible({ timeout: 10_000 });
  await action.click();
};

const expectItemInStarredTree = async (
  page: Page,
  itemName: string,
  ancestorTitles: string[] = [],
) => {
  await openTreeNode(page, "Starred");
  for (const ancestorTitle of ancestorTitles) {
    await openTreeNode(page, ancestorTitle);
  }
  await getItemTree(page, itemName);
};

export const verifyItemIsStarred = async (
  page: Page,
  itemName: string,
  ancestorTitles: string[] = [],
) => {
  try {
    await expectItemInStarredTree(page, itemName, ancestorTitles);
  } catch {
    await clickToFavorites(page);
    await expectRowItem(page, itemName);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expectItemInStarredTree(page, itemName, ancestorTitles);
  }
  await clickToFavorites(page);
  await expectRowItem(page, itemName);
};

export const verifyFileIsStarredOnlyInFavoritesPage = async (
  page: Page,
  itemName: string,
) => {
  await openTreeNode(page, "Starred");
  const itemTree = page.getByRole("treeitem").filter({ hasText: itemName }).first();
  await expect(itemTree).not.toBeVisible({ timeout: 20_000 });
  await clickToFavorites(page);
  await expectRowItem(page, itemName);
};

export const verifyItemIsNotStarred = async (page: Page, itemName: string) => {
  await openTreeNode(page, "Starred");
  const itemTree = page.getByRole("treeitem").filter({ hasText: itemName }).first();
  await expect(itemTree).not.toBeVisible({ timeout: 20_000 });
  await clickToFavorites(page);
  await expectRowItemIsNotVisible(page, itemName, { timeoutMs: 20_000 });
};

export const starItem = async (page: Page, itemName: string) => {
  await clearExplorerSelectionIfPresent(page);
  const favoriteMutation = waitForFavoriteMutation(page, "POST");
  await clickFavoriteContextMenuAction(page, itemName, /^(Star|Favoris)$/i);
  await favoriteMutation;
  await clickToFavorites(page);
  await expectRowItem(page, itemName);
};

export const unstarItem = async (page: Page, itemName: string) => {
  await clearExplorerSelectionIfPresent(page);
  const favoriteMutation = waitForFavoriteMutation(page, "DELETE");
  await clickFavoriteContextMenuAction(
    page,
    itemName,
    /^(Unstar|Retirer des favoris)$/i,
  );
  await favoriteMutation;
  await clickToFavorites(page);
  await expectRowItemIsNotVisible(page, itemName, { timeoutMs: 20_000 });
};
