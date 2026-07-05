import { Item, ItemType } from "@/features/drivers/types";
import type { EmbeddedExplorerProps } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorer";

type CreateFolderTargetEmbeddedExplorerPropsParams = Pick<
  EmbeddedExplorerProps,
  "breadcrumbsRight" | "initialFolderId" | "itemsFilter"
> & {
  disableItemDragAndDrop?: boolean;
};

export const createFolderTargetEmbeddedExplorerProps = ({
  breadcrumbsRight,
  disableItemDragAndDrop,
  initialFolderId,
  itemsFilter,
}: CreateFolderTargetEmbeddedExplorerPropsParams): EmbeddedExplorerProps => ({
  breadcrumbsRight,
  initialFolderId,
  isCompact: true,
  gridProps: {
    disableItemDragAndDrop,
    disableKeyboardNavigation: true,
    enableMetaKeySelection: false,
    gridActionsCell: () => null,
  },
  itemsFilter,
  itemsFilters: {
    type: ItemType.FOLDER,
  },
});

type ResolveCurrentFolderTargetParams<TItem extends Pick<Item, "id">> = {
  currentItem?: TItem;
  currentItemId?: string | null;
  selectedItems: TItem[];
};

export const resolveCurrentFolderTarget = <TItem extends Pick<Item, "id">>({
  currentItem,
  currentItemId,
  selectedItems,
}: ResolveCurrentFolderTargetParams<TItem>) => {
  const selectedItem =
    selectedItems.length === 1 ? selectedItems[0] : undefined;

  return {
    folderId: selectedItem?.id ?? currentItemId ?? undefined,
    folderItem: selectedItem ?? currentItem,
  };
};
