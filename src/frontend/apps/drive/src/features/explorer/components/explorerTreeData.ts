import { Item, TreeItem } from "@/features/drivers/types";
import { getItemTitle } from "../utils/utils";
import { TreeViewNodeTypeEnum } from "@gouvfr-lasuite/ui-kit";

export const generateTreeId = (
  originalId: string,
  parentTreeId?: string,
  isFavoriteItem?: boolean,
): string => {
  if (!isFavoriteItem) {
    return originalId;
  }

  return parentTreeId ? `${parentTreeId}::${originalId}` : originalId;
};

export const getOriginalIdFromTreeId = (treeId: string): string => {
  const parts = treeId.split("::");
  return parts[parts.length - 1];
};

export const itemToTreeItem = (
  item: Item,
  parentTreeId?: string,
  isFavoriteItem?: boolean,
): TreeItem => {
  const originalId = item.id;
  const treeId = generateTreeId(originalId, parentTreeId, isFavoriteItem);

  return {
    ...item,
    id: treeId,
    originalId,
    parentId: parentTreeId,
    childrenCount: item.numchild_folder ?? 0,
    children:
      item.children?.map((child) =>
        itemToTreeItem(child, treeId, isFavoriteItem),
      ) ?? [],
    nodeType: TreeViewNodeTypeEnum.NODE,
    title: getItemTitle(item),
  };
};

export const itemsToTreeItems = (
  items: Item[],
  parentId?: string,
): TreeItem[] => {
  return items.map((item) => itemToTreeItem(item, parentId));
};
