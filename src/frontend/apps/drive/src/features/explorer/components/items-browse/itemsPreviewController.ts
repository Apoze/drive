import { Item } from "@/features/drivers/types";
import { createPreviewCurrentItemController } from "@/features/ui/preview/files-preview/previewCurrentItemController";

type ItemsPreviewControllerParams = {
  setPreviewCurrentItem: (item: Item | undefined) => void;
  replacePreviewItems: (items: Item[]) => void;
};

export const createItemsPreviewController = ({
  setPreviewCurrentItem,
  replacePreviewItems,
}: ItemsPreviewControllerParams) => {
  const previewCurrentItemController = createPreviewCurrentItemController<Item>({
    setPreviewCurrentItem,
  });

  const openPreview = (item: Item, items: Item[]) => {
    replacePreviewItems(items);
    previewCurrentItemController.setPreviewCurrentItem(item);
  };

  const openSinglePreview = (item: Item) => {
    openPreview(item, [item]);
  };

  return {
    ...previewCurrentItemController,
    replacePreviewItems,
    openPreview,
    openSinglePreview,
  };
};

export type ItemsPreviewController = ReturnType<
  typeof createItemsPreviewController
>;
