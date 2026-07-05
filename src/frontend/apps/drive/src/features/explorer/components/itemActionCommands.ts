import { DefaultRoute } from "@/utils/defaultRoutes";
import { Item, ItemType } from "@/features/drivers/types";
import { itemToTreeItem } from "./GlobalExplorerContext";

export const canDeleteItems = (items: Item[]) => {
  return items.length > 0 && items.every((item) => item.abilities?.destroy);
};

export const getDeleteItemIds = (items: Item[]) => {
  return items.map((item) => item.id);
};

export const applyFavoriteTreeSync = ({
  item,
  addFavoriteChild,
}: {
  item: Item;
  addFavoriteChild?: (item: ReturnType<typeof itemToTreeItem>) => void;
}) => {
  if (item.type !== ItemType.FOLDER || !addFavoriteChild) {
    return;
  }

  addFavoriteChild(itemToTreeItem(item, DefaultRoute.FAVORITES, true));
};

export const handleFavoriteCommand = async ({
  createFavoriteItem,
  effectiveItemId,
  item,
  addFavoriteChild,
}: {
  createFavoriteItem: (
    itemId: string,
    options?: { onSuccess?: () => void },
  ) => Promise<unknown>;
  effectiveItemId: string;
  item: Item;
  addFavoriteChild?: (item: ReturnType<typeof itemToTreeItem>) => void;
}) => {
  await createFavoriteItem(effectiveItemId, {
    onSuccess: () => {
      applyFavoriteTreeSync({ item, addFavoriteChild });
    },
  });
};
