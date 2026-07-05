import { Dispatch, SetStateAction } from "react";

type SelectionControllerParams<TItem> = {
  setSelectedItems: Dispatch<SetStateAction<TItem[]>>;
};

export const createSelectionController = <TItem>({
  setSelectedItems,
}: SelectionControllerParams<TItem>) => {
  const clearSelection = () => {
    setSelectedItems([]);
  };

  const replaceSelection = (items: TItem[]) => {
    setSelectedItems(items);
  };

  const selectSingleItem = (item: TItem) => {
    replaceSelection([item]);
  };

  return {
    setSelectedItems,
    clearSelection,
    replaceSelection,
    selectSingleItem,
  };
};

export type SelectionController<TItem> = ReturnType<
  typeof createSelectionController<TItem>
>;
