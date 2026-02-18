import { expect } from "@playwright/test";

import { PageOrLocator } from "./types-utils";

export const getMoveFolderModal = async (page: PageOrLocator) => {
  const moveFolderModal = page.getByLabel("Move folder modal");
  await expect(moveFolderModal).toBeVisible();
  return moveFolderModal;
};

export const getMoveConfirmationModal = async (page: PageOrLocator) => {
  const moveConfirmationModal = page.getByLabel("Move confirmation modal");
  await expect(moveConfirmationModal).toBeVisible();
  return moveConfirmationModal;
};

const acceptMoveConfirmationIfPresent = async (page: PageOrLocator) => {
  const moveConfirmationModal = page.getByLabel("Move confirmation modal");
  try {
    await moveConfirmationModal.waitFor({ state: "visible", timeout: 5000 });
  } catch {
    return;
  }
  await expect(
    moveConfirmationModal.getByText("Transfer rights")
  ).toBeVisible();
  await expect(
    moveConfirmationModal.getByText("You are about to move the")
  ).toBeVisible();
  await moveConfirmationModal
    .getByRole("button", { name: "Move anyway" })
    .click();
};
export const expectMoveFolderModal = async (page: PageOrLocator) => {
  await getMoveFolderModal(page); // getMoveFolderModal already checks if the modal is visible
};

export const acceptMoveItem = async (page: PageOrLocator) => {
  const moveFolderModal = await getMoveFolderModal(page);
  await moveFolderModal.getByRole("button", { name: "Move here" }).click();
  await acceptMoveConfirmationIfPresent(page);
};

export const searchAndSelectItem = async (
  page: PageOrLocator,
  itemName: string
) => {
  const moveFolderModal = await getMoveFolderModal(page);
  await moveFolderModal.getByPlaceholder("Search for a folder").click();
  await moveFolderModal.getByPlaceholder("Search for a folder").fill(itemName);
  await expect(moveFolderModal.getByText("Search results")).toBeVisible();
  const escaped = itemName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const folderRow = moveFolderModal
    .getByRole("row", { name: new RegExp(`^${escaped}\\b`, "i") })
    .first();
  await expect(folderRow).toBeVisible({ timeout: 20_000 });
  await folderRow.dblclick();
};

export const clickAndAcceptMoveToRoot = async (page: PageOrLocator) => {
  const moveFolderModal = await getMoveFolderModal(page);
  await moveFolderModal.getByRole("button", { name: "Move to root" }).click();
  const moveConfirmationModal = page.getByLabel("Move confirmation modal");
  try {
    await moveConfirmationModal.waitFor({ state: "visible", timeout: 5000 });
  } catch {
    return;
  }
  await expect(
    moveConfirmationModal.getByText(
      "Moved documents will be accessible via your 'My files' tab. People who had access to the documents only through inherited rights from a parent will no longer be able to access them."
    )
  ).toBeVisible();
  await moveConfirmationModal
    .getByRole("button", { name: "Move anyway" })
    .click();
};
