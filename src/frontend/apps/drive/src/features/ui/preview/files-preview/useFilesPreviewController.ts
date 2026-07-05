import { useMemo } from "react";
import { type FilePreviewType } from "./previewSource";

type PreviewControllerItem = {
  id: string;
};

type UseFilesPreviewControllerParams<TItem extends PreviewControllerItem> = {
  currentItem?: TItem;
  items: TItem[];
  setPreviewCurrentItem?: (item?: TItem) => void;
  isPreviewableItem: (item: TItem) => boolean;
  mapItemToPreviewFile: (item: TItem) => FilePreviewType;
};

export const useFilesPreviewController = <
  TItem extends PreviewControllerItem,
>({
  currentItem,
  items,
  setPreviewCurrentItem,
  isPreviewableItem,
  mapItemToPreviewFile,
}: UseFilesPreviewControllerParams<TItem>) => {
  const files = useMemo(
    () => items.filter(isPreviewableItem).map(mapItemToPreviewFile),
    [items, isPreviewableItem, mapItemToPreviewFile],
  );

  const handleClosePreview = () => {
    setPreviewCurrentItem?.(undefined);
  };

  const handleChangePreviewItem = (file?: FilePreviewType) => {
    const nextItem = items.find((item) => item.id === file?.id);
    setPreviewCurrentItem?.(nextItem);
  };

  return {
    files,
    isOpen: Boolean(currentItem),
    openedFileId: currentItem?.id,
    handleClosePreview,
    handleChangePreviewItem,
  };
};
