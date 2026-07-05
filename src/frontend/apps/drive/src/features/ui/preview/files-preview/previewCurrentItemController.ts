type PreviewCurrentItemControllerParams<TItem> = {
  previewItem?: TItem;
  setPreviewCurrentItem: (item: TItem | undefined) => void;
};

export const createPreviewCurrentItemController = <TItem>({
  previewItem,
  setPreviewCurrentItem,
}: PreviewCurrentItemControllerParams<TItem>) => {
  const closePreview = () => {
    setPreviewCurrentItem(undefined);
  };

  const closePreviewIf = (predicate: (item: TItem) => boolean) => {
    if (previewItem && predicate(previewItem)) {
      closePreview();
    }
  };

  return {
    previewItem,
    setPreviewCurrentItem,
    closePreview,
    closePreviewIf,
  };
};

export type PreviewCurrentItemController<TItem> = ReturnType<
  typeof createPreviewCurrentItemController<TItem>
>;
