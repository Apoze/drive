import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  type Item,
} from "@/features/drivers/types";
import {
  addItemToTopOfPaginatedList,
  removeItemsFromPaginatedList,
  updateItemInPaginatedList,
  useAddItemToPaginatedList,
  useRemoveItemsFromPaginatedList,
  useUpdateItemInPaginatedList,
} from "../useOptimisticPagination";
import { QueryClient, useQueryClient } from "@tanstack/react-query";

jest.mock("@tanstack/react-query", () => {
  const actual = jest.requireActual("@tanstack/react-query");
  return {
    ...actual,
    useQueryClient: jest.fn(),
  };
});

const mockedUseQueryClient = jest.mocked(useQueryClient);

const buildItem = (id: string, overrides: Partial<Item> = {}): Item => ({
  id,
  title: `Item ${id}`,
  filename: `Item-${id}.txt`,
  creator: {
    id: "owner-1",
    full_name: "Owner",
    short_name: "OW",
  },
  type: ItemType.FILE,
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: LinkReach.RESTRICTED,
  computed_link_role: LinkRole.READER,
  upload_state: ItemUploadState.READY,
  updated_at: new Date("2026-03-31T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-31T00:00:00Z"),
  path: `root.${id}`,
  abilities: {
    accesses_manage: false,
    accesses_view: true,
    children_create: false,
    children_list: false,
    destroy: false,
    favorite: false,
    invite_owner: false,
    link_configuration: false,
    media_auth: false,
    move: false,
    link_select_options: {
      [LinkReach.RESTRICTED]: null,
      [LinkReach.AUTHENTICATED]: null,
      [LinkReach.PUBLIC]: null,
    },
    partial_update: true,
    restore: false,
    retrieve: true,
    tree: false,
    update: true,
    upload_ended: true,
  },
  ...overrides,
});

const buildInfiniteData = (...pages: Item[][]) => ({
  pages: pages.map((children) => ({ children })),
});

describe("useOptimisticPagination", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    mockedUseQueryClient.mockReturnValue(queryClient);
  });

  it("adds a new item to the top of every matching paginated query and avoids duplicates", () => {
    const existing = buildItem("item-1");
    const other = buildItem("item-2");
    const newItem = buildItem("item-3");

    queryClient.setQueryData(
      ["items", "parent-1", "children"],
      buildInfiniteData([existing, other]),
    );
    queryClient.setQueryData(
      ["items", "parent-1", "children", "filtered"],
      buildInfiniteData([other]),
    );
    queryClient.setQueryData(["items", "other-parent"], buildInfiniteData([]));

    addItemToTopOfPaginatedList(queryClient, ["items", "parent-1", "children"], newItem);
    addItemToTopOfPaginatedList(queryClient, ["items", "parent-1", "children"], newItem);

    expect(
      queryClient.getQueryData<{ pages: Array<{ children: Item[] }> }>([
        "items",
        "parent-1",
        "children",
      ])?.pages[0].children.map((item) => item.id),
    ).toEqual(["item-3", "item-1", "item-2"]);
    expect(
      queryClient.getQueryData<{ pages: Array<{ children: Item[] }> }>([
        "items",
        "parent-1",
        "children",
        "filtered",
      ])?.pages[0].children.map((item) => item.id),
    ).toEqual(["item-3", "item-2"]);
    expect(
      queryClient.getQueryData<{ pages: Array<{ children: Item[] }> }>([
        "items",
        "other-parent",
      ])?.pages[0].children.map((item) => item.id),
    ).toEqual([]);
  });

  it("removes matching ids from every page of the paginated list", () => {
    queryClient.setQueryData(
      ["items", "trash"],
      buildInfiniteData(
        [buildItem("item-1"), buildItem("item-2")],
        [buildItem("item-3"), buildItem("item-4")],
      ),
    );

    removeItemsFromPaginatedList(queryClient, ["items", "trash"], ["item-2", "item-3"]);

    expect(
      queryClient.getQueryData<{ pages: Array<{ children: Item[] }> }>([
        "items",
        "trash",
      ])?.pages.map((page) => page.children.map((item) => item.id)),
    ).toEqual([["item-1"], ["item-4"]]);
  });

  it("updates a partial item across matching paginated queries", () => {
    queryClient.setQueryData(
      ["items", "favorites"],
      buildInfiniteData([buildItem("item-1"), buildItem("item-2")]),
    );

    updateItemInPaginatedList(
      queryClient,
      ["items", "favorites"],
      "item-2",
      { title: "Renamed", is_favorite: true },
    );

    const updated = queryClient.getQueryData<{ pages: Array<{ children: Item[] }> }>([
      "items",
      "favorites",
    ])?.pages[0].children.find((item) => item.id === "item-2");

    expect(updated).toMatchObject({
      id: "item-2",
      title: "Renamed",
      is_favorite: true,
    });
  });

  it("hook wrappers reuse the current query client for add, remove and update", () => {
    const item1 = buildItem("item-1");
    const item2 = buildItem("item-2");
    const item3 = buildItem("item-3");

    queryClient.setQueryData(
      ["items", "wrapper-parent", "children"],
      buildInfiniteData([item1, item2]),
    );

    const addItem = useAddItemToPaginatedList();
    const removeItems = useRemoveItemsFromPaginatedList();
    const updateItem = useUpdateItemInPaginatedList();

    addItem(["items", "wrapper-parent", "children"], item3);
    updateItem(["items", "wrapper-parent", "children"], "item-2", {
      title: "Updated title",
    });
    removeItems(["items", "wrapper-parent", "children"], ["item-1"]);

    expect(
      queryClient.getQueryData<{ pages: Array<{ children: Item[] }> }>([
        "items",
        "wrapper-parent",
        "children",
      ])?.pages[0].children.map((item) => ({
        id: item.id,
        title: item.title,
      })),
    ).toEqual([
      { id: "item-3", title: "Item item-3" },
      { id: "item-2", title: "Updated title" },
    ]);
  });
});
