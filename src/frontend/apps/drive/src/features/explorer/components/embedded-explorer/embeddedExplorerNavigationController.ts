type EmbeddedExplorerNavigationControllerParams = {
  clearSelection?: () => void;
  setCurrentItemId?: (itemId: string | null) => void;
  resetSearch: () => void;
};

export const createEmbeddedExplorerNavigationController = ({
  clearSelection,
  setCurrentItemId,
  resetSearch,
}: EmbeddedExplorerNavigationControllerParams) => {
  const navigateToItem = (itemId: string | null) => {
    clearSelection?.();
    setCurrentItemId?.(itemId);
    resetSearch();
  };

  const navigateToRoot = () => {
    navigateToItem(null);
  };

  const navigateToBreadcrumbItem = (itemId: string) => {
    if (itemId === "search") {
      navigateToRoot();
      return;
    }
    navigateToItem(itemId);
  };

  return {
    navigateToItem,
    navigateToRoot,
    navigateToBreadcrumbItem,
  };
};

export type EmbeddedExplorerNavigationController = ReturnType<
  typeof createEmbeddedExplorerNavigationController
>;
