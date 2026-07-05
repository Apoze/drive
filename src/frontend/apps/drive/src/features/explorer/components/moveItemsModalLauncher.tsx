import React from "react";
import { Item } from "@/features/drivers/types";
import { ExplorerMoveFolder } from "./modals/move/ExplorerMoveFolderModal";

export const MoveItemsModalLauncher = ({
  initialFolderId,
  isOpen,
  itemsToMove,
  onClose,
}: {
  initialFolderId?: string;
  isOpen: boolean;
  itemsToMove: Item[];
  onClose: () => void;
}) => {
  if (!isOpen || itemsToMove.length === 0) {
    return null;
  }

  return (
    <ExplorerMoveFolder
      isOpen={isOpen}
      onClose={onClose}
      itemsToMove={itemsToMove}
      initialFolderId={initialFolderId}
    />
  );
};
