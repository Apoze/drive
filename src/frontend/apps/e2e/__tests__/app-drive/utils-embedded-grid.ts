import { expect } from "@playwright/test";
import { PageOrLocator } from "./utils/types-utils";

const DEFAULT_ROW_TIMEOUT_MS = 20_000;

const getExplorerTable = (page: PageOrLocator) => {
  return page
    .getByRole("table")
    // The embedded grid uses ARIA `cell` for header cells in this app.
    .filter({ has: page.getByRole("cell", { name: /^Name$/i }) })
    .first();
};

const getRowItemLocator = (page: PageOrLocator, itemName: string) => {
  const table = getExplorerTable(page);
  // In the explorer grid, the name is rendered as a nested button within the cell.
  // `.last()` targets the clickable nested button (there is often an outer wrapper).
  return table.getByRole("button", { name: itemName, exact: true }).last();
};

export const expectRowItem = async (page: PageOrLocator, itemName: string) => {
  const item = getRowItemLocator(page, itemName);
  await expect(item).toBeVisible({ timeout: DEFAULT_ROW_TIMEOUT_MS });
};

export const expectRowItemIsNotVisible = async (
  page: PageOrLocator,
  itemName: string
) => {
  const item = getRowItemLocator(page, itemName);
  await expect(item).not.toBeVisible();
};

export const getRowItem = async (page: PageOrLocator, itemName: string) => {
  const item = getRowItemLocator(page, itemName);
  await expect(item).toBeVisible({ timeout: DEFAULT_ROW_TIMEOUT_MS });
  return item;
};

export const getRowItemActions = async (
  page: PageOrLocator,
  itemName: string
) => {
  const table = getExplorerTable(page);
  const actions = table
    .getByRole("button", {
      name: `More actions for ${itemName}`,
      exact: true,
    })
    .last();
  await expect(actions).toBeVisible({ timeout: DEFAULT_ROW_TIMEOUT_MS });
  return actions;
};

export const clickOnRowItemActions = async (
  page: PageOrLocator,
  itemName: string,
  actionName: string
) => {
  const actions = await getRowItemActions(page, itemName);
  await actions.click({ force: true }); // Because dnd-kit add an aria-disabled attribute on parent and playwright don't interact with it
  const action = page.getByRole("menuitem", { name: actionName });
  await expect(action).toBeVisible();
  await action.click();
};
