import { Item } from "@/features/drivers/types";

type RightPanelControllerParams = {
  rightPanelForcedItem?: Item;
  setRightPanelForcedItem: (item: Item | undefined) => void;
  rightPanelOpen: boolean;
  setRightPanelOpen: (open: boolean) => void;
};

export const createRightPanelController = ({
  rightPanelForcedItem,
  setRightPanelForcedItem,
  rightPanelOpen,
  setRightPanelOpen,
}: RightPanelControllerParams) => {
  const openRightPanelForItem = (item: Item) => {
    setRightPanelForcedItem(item);
    setRightPanelOpen(true);
  };

  const closeRightPanel = () => {
    setRightPanelOpen(false);
  };

  const clearRightPanelItem = () => {
    setRightPanelForcedItem(undefined);
  };

  const replaceRightPanelItem = (item: Item | undefined) => {
    setRightPanelForcedItem(item);
  };

  const replaceRightPanelItemIfCurrent = (
    currentItemId: string,
    nextItem: Item,
  ) => {
    if (rightPanelForcedItem?.id === currentItemId) {
      replaceRightPanelItem(nextItem);
    }
  };

  const closeRightPanelIf = (predicate: (item: Item) => boolean) => {
    if (rightPanelForcedItem && predicate(rightPanelForcedItem)) {
      clearRightPanelItem();
      closeRightPanel();
    }
  };

  const closeRightPanelIfCurrent = (itemId: string) => {
    closeRightPanelIf((item) => item.id === itemId);
  };

  const closeRightPanelIfIncluded = (
    items: Array<Pick<Item, "id">> | string[],
  ) => {
    const itemIds = new Set(
      items.map((item) => (typeof item === "string" ? item : item.id)),
    );
    closeRightPanelIf((item) => itemIds.has(item.id));
  };

  return {
    rightPanelForcedItem,
    rightPanelOpen,
    setRightPanelForcedItem,
    setRightPanelOpen,
    openRightPanelForItem,
    closeRightPanel,
    clearRightPanelItem,
    replaceRightPanelItem,
    replaceRightPanelItemIfCurrent,
    closeRightPanelIfCurrent,
    closeRightPanelIfIncluded,
  };
};

export type RightPanelController = ReturnType<
  typeof createRightPanelController
>;
