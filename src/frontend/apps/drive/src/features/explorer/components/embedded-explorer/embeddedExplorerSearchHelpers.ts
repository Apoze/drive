import { Item, ItemBreadcrumb } from "@/features/drivers/types";
import { ItemFilters } from "@/features/drivers/Driver";

export const EMBEDDED_SEARCH_RESULTS_BREADCRUMB_ID = "search";

export const buildEmbeddedExplorerSearchFilters = (
  searchQuery: string,
  itemsFilters?: ItemFilters,
) => ({
  title: searchQuery,
  ...itemsFilters,
});

export const scheduleEmbeddedExplorerSearch = ({
  query,
  timeoutRef,
  setInputSearchValue,
  setSearchQuery,
  delayMs = 300,
  setTimeoutFn = setTimeout,
  clearTimeoutFn = clearTimeout,
}: {
  query: string;
  timeoutRef: { current: NodeJS.Timeout | null };
  setInputSearchValue: (value: string) => void;
  setSearchQuery: (value: string) => void;
  delayMs?: number;
  setTimeoutFn?: typeof setTimeout;
  clearTimeoutFn?: typeof clearTimeout;
}) => {
  if (timeoutRef.current) {
    clearTimeoutFn(timeoutRef.current);
  }

  setInputSearchValue(query);
  if (query === "") {
    setSearchQuery("");
    timeoutRef.current = null;
    return;
  }

  timeoutRef.current = setTimeoutFn(() => {
    setSearchQuery(query);
  }, delayMs);
};

export const resolveEmbeddedExplorerItems = ({
  currentItemId,
  rootItems,
  itemChildren,
  searchItems,
  searchQuery,
  isSearchItemsLoading,
  previousItems,
  itemsFilter,
  mapItem,
}: {
  currentItemId: string | null | undefined;
  rootItems: Item[];
  itemChildren: Item[] | undefined;
  searchItems: Item[] | undefined;
  searchQuery: string;
  isSearchItemsLoading: boolean;
  previousItems: Item[];
  itemsFilter?: (items: Item[]) => Item[];
  mapItem?: (item: Item) => Item;
}): Item[] | undefined => {
  if (itemChildren === undefined && currentItemId) {
    return undefined;
  }

  if (isSearchItemsLoading) {
    return previousItems;
  }

  let items: Item[] = [];

  if (searchQuery !== "") {
    items = searchItems ?? [];
  } else if (currentItemId === null) {
    items = rootItems;
  } else {
    items = itemChildren ?? [];
  }

  if (itemsFilter) {
    items = itemsFilter(items);
  }

  if (mapItem) {
    items = items.map(mapItem);
  }

  return items;
};

export const buildEmbeddedExplorerForcedBreadcrumbs = ({
  searchQuery,
  title,
}: {
  searchQuery: string;
  title: string;
}): ItemBreadcrumb[] | undefined => {
  if (searchQuery === "") {
    return undefined;
  }

  return [
    {
      id: EMBEDDED_SEARCH_RESULTS_BREADCRUMB_ID,
      title,
      path: "",
      depth: 0,
      main_workspace: false,
    },
  ];
};
