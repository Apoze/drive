import { ItemType, type Item } from "@/features/drivers/types";
import {
  buildEmbeddedExplorerForcedBreadcrumbs,
  buildEmbeddedExplorerSearchFilters,
  EMBEDDED_SEARCH_RESULTS_BREADCRUMB_ID,
  resolveEmbeddedExplorerItems,
  scheduleEmbeddedExplorerSearch,
} from "../embeddedExplorerSearchHelpers";

const buildItem = (overrides: Partial<Item> = {}): Item =>
  ({
    id: "item-1",
    title: "Report",
    filename: "Report.txt",
    creator: {
      id: "user-1",
      full_name: "Jane Doe",
      short_name: "JD",
    },
    type: ItemType.FILE,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-22T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-22T00:00:00Z"),
    path: "/Report.txt",
    abilities: {} as never,
    ...overrides,
  }) as Item;

describe("embeddedExplorerSearchHelpers", () => {
  it("builds the embedded search query and forced breadcrumb consistently", () => {
    expect(
      buildEmbeddedExplorerSearchFilters("report", {
        workspace: "workspace-1",
      }),
    ).toEqual({
      title: "report",
      workspace: "workspace-1",
    });

    expect(
      buildEmbeddedExplorerForcedBreadcrumbs({
        searchQuery: "report",
        title: "Search results",
      }),
    ).toEqual([
      {
        id: EMBEDDED_SEARCH_RESULTS_BREADCRUMB_ID,
        title: "Search results",
        path: "",
        depth: 0,
        main_workspace: false,
      },
    ]);
    expect(
      buildEmbeddedExplorerForcedBreadcrumbs({
        searchQuery: "",
        title: "Search results",
      }),
    ).toBeUndefined();
  });

  it("schedules and resets the embedded search query with debounce", () => {
    jest.useFakeTimers();
    const timeoutRef = { current: null as NodeJS.Timeout | null };
    const setInputSearchValue = jest.fn();
    const setSearchQuery = jest.fn();

    scheduleEmbeddedExplorerSearch({
      query: "rep",
      timeoutRef,
      setInputSearchValue,
      setSearchQuery,
    });
    scheduleEmbeddedExplorerSearch({
      query: "repo",
      timeoutRef,
      setInputSearchValue,
      setSearchQuery,
    });

    expect(setInputSearchValue).toHaveBeenNthCalledWith(1, "rep");
    expect(setInputSearchValue).toHaveBeenNthCalledWith(2, "repo");
    expect(setSearchQuery).not.toHaveBeenCalled();

    jest.runAllTimers();
    expect(setSearchQuery).toHaveBeenCalledWith("repo");

    scheduleEmbeddedExplorerSearch({
      query: "",
      timeoutRef,
      setInputSearchValue,
      setSearchQuery,
    });
    expect(setSearchQuery).toHaveBeenLastCalledWith("");
    jest.useRealTimers();
  });

  it("resolves root, children and search-result items without changing embedded semantics", () => {
    const rootItems = [buildItem({ id: "root-1" })];
    const childItems = [buildItem({ id: "child-1" })];
    const searchItems = [buildItem({ id: "search-1", main_workspace: true })];

    expect(
      resolveEmbeddedExplorerItems({
        currentItemId: null,
        rootItems,
        itemChildren: undefined,
        searchItems: undefined,
        searchQuery: "",
        isSearchItemsLoading: false,
        previousItems: [],
      }),
    ).toEqual(rootItems);

    expect(
      resolveEmbeddedExplorerItems({
        currentItemId: "folder-1",
        rootItems,
        itemChildren: childItems,
        searchItems: undefined,
        searchQuery: "",
        isSearchItemsLoading: false,
        previousItems: [],
      }),
    ).toEqual(childItems);

    expect(
      resolveEmbeddedExplorerItems({
        currentItemId: "folder-1",
        rootItems,
        itemChildren: childItems,
        searchItems,
        searchQuery: "report",
        isSearchItemsLoading: false,
        previousItems: [],
        mapItem: (item) =>
          item.main_workspace
            ? {
                ...item,
                title: "Main workspace",
              }
            : item,
      }),
    ).toEqual([
      expect.objectContaining({
        id: "search-1",
        title: "Main workspace",
      }),
    ]);

    expect(
      resolveEmbeddedExplorerItems({
        currentItemId: "folder-1",
        rootItems,
        itemChildren: childItems,
        searchItems,
        searchQuery: "report",
        isSearchItemsLoading: true,
        previousItems: rootItems,
      }),
    ).toEqual(rootItems);
  });
});
