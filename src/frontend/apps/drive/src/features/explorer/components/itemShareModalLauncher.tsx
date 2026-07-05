import React from "react";
import { Item } from "@/features/drivers/types";
import { ItemShareModal } from "./modals/share/ItemShareModal";

export const ItemShareModalLauncher = ({
  isOpen,
  item,
  onClose,
}: {
  isOpen: boolean;
  item?: Item | null;
  onClose: () => void;
}) => {
  if (!isOpen || !item?.abilities?.accesses_view) {
    return null;
  }

  return <ItemShareModal isOpen={isOpen} onClose={onClose} item={item} />;
};
