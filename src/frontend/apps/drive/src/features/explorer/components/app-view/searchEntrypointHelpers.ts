import { ItemFilters } from "@/features/drivers/Driver";
import { Item } from "@/features/drivers/types";

export const isExplorerSearchShortcut = (event: {
  key: string;
  metaKey?: boolean;
  ctrlKey?: boolean;
}) => event.key === "k" && Boolean(event.metaKey || event.ctrlKey);

export const getHeaderSearchDefaultFilters = ({
  currentItem,
  isMinimalLayout,
}: {
  currentItem?: Item;
  isMinimalLayout: boolean;
}): ItemFilters => {
  if (!isMinimalLayout) {
    return {};
  }

  return {
    workspace: currentItem?.parents?.[0]?.id ?? currentItem?.id,
  };
};
