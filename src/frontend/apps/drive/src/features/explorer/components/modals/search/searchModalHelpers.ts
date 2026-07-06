import { Item, ItemType } from "@/features/drivers/types";
import { ItemFilters } from "@/features/drivers/Driver";
import { openWopiInNewTab } from "@/features/ui/preview/wopi/openWopi";

export const shouldClearExplorerSearchResults = (
  inputValue: string,
  filters: ItemFilters,
) => inputValue === "" && Object.keys(filters).length === 0;

export const buildExplorerSearchQuery = (
  filters: ItemFilters,
  inputValue: string,
) => ({
  ...filters,
  title: inputValue,
});

export const activateExplorerSearchItem = ({
  item,
  onNavigate,
  openSinglePreview,
  onClose,
  onTrashFolderBlocked,
  onFileActivated,
}: {
  item: Item;
  onNavigate: (event: {
    item: Item;
    type: "item";
  }) => void;
  openSinglePreview: (item: Item) => void;
  onClose: () => void;
  onTrashFolderBlocked: () => void;
  onFileActivated?: () => void;
}) => {
  if (item.type === ItemType.FOLDER) {
    if (item.deleted_at) {
      onTrashFolderBlocked();
      return;
    }

    onNavigate({
      item,
      type: "item",
    });
    onClose();
    return;
  }

  if (item.is_wopi_supported) {
    openWopiInNewTab(item.id);
  } else {
    openSinglePreview(item);
  }
  onFileActivated?.();
};
