import { Item, ItemType } from "@/features/drivers/types";
import { MountExplorerItem } from "./mountExplorerItems";
import {
  getParentMountPath,
  isSameOrDescendantMountPath,
} from "./mountBulkActions";

export const isMountExplorerItem = (item: Item): item is MountExplorerItem => {
  return "mountMeta" in item;
};

export const canMountItemReceiveDrop = (item: Item) => {
  if (!isMountExplorerItem(item)) {
    return false;
  }
  return (
    item.type === ItemType.FOLDER &&
    item.mountMeta.entryType === "folder" &&
    Boolean(item.abilities.children_list)
  );
};

export const canMountItemsDrop = (activeItem: Item, overItem: Item) => {
  if (!isMountExplorerItem(activeItem) || !isMountExplorerItem(overItem)) {
    return false;
  }

  if (activeItem.mountMeta.mountId !== overItem.mountMeta.mountId) {
    return false;
  }

  if (!activeItem.mountMeta.abilities?.move || !canMountItemReceiveDrop(overItem)) {
    return false;
  }

  if (activeItem.id === overItem.id) {
    return false;
  }

  const activePath = activeItem.mountMeta.normalizedPath;
  const overPath = overItem.mountMeta.normalizedPath;

  if (activeItem.mountMeta.entryType === "folder") {
    if (isSameOrDescendantMountPath(activePath, overPath)) {
      return false;
    }
  }

  if (getParentMountPath(activePath) === overPath) {
    return false;
  }

  return true;
};
