import React from "react";
import { Item } from "@/features/drivers/types";
import { getRuntimeConfig } from "@/features/config/runtimeConfig";
import { StorageTransferModal } from "@/features/storage/StorageTransferModal";
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

  if (getRuntimeConfig()?.STORAGE_UNIFIED_ENABLED) {
    return (
      <StorageTransferModal items={itemsToMove} mode="move" onClose={onClose} />
    );
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
