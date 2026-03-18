import { Page, expect } from "@playwright/test";
import { getItemTree, openTreeNode } from "../utils-tree";
import {
  clickOnRowItemActions,
  expectRowItem,
  expectRowItemIsNotVisible,
} from "../utils-embedded-grid";
import { clickToFavorites } from "../utils-navigate";

export const verifyItemIsStarred = async (
  page: Page,
  itemName: string,
  ancestorTitles: string[] = [],
) => {
  await openTreeNode(page, "Starred");
  for (const ancestorTitle of ancestorTitles) {
    await openTreeNode(page, ancestorTitle);
  }
  await getItemTree(page, itemName); // get and verify the item is in the tree
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
  await clickOnRowItemActions(page, itemName, "Star");
};

export const unstarItem = async (page: Page, itemName: string) => {
  await clickOnRowItemActions(page, itemName, "Unstar");
};
