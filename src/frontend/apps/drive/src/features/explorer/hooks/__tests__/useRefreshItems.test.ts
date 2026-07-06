import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  type Item,
} from "@/features/drivers/types";
import { useQueryClient } from "@tanstack/react-query";
import { useTreeContext } from "@gouvfr-lasuite/ui-kit";
import { generateTreeId } from "../../components/GlobalExplorerContext";
import * as refreshItemsModule from "../useRefreshItems";
import { BatchDeleteError } from "@/features/errors/BatchDeleteError";
import {
  useDeleteMutationCallbacks,
  useGetQueryKeyToRefresh,
  useOnSuccessAccessOrInvitationMutation,
  useRefreshFavoriteCache,
  useRefreshItemCache,
  useRefreshQueryCacheAfterMutation,
} from "../useRefreshItems";
import {
  useRemoveItemsFromPaginatedList,
  useUpdateItemInPaginatedList,
} from "../useOptimisticPagination";

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: jest.fn(),
}));

jest.mock("../useOptimisticPagination", () => ({
  useRemoveItemsFromPaginatedList: jest.fn(),
  useUpdateItemInPaginatedList: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  useTreeContext: jest.fn(),
}));

jest.mock("../../components/GlobalExplorerContext", () => ({
  generateTreeId: jest.fn(),
}));

const mockedUseQueryClient = jest.mocked(useQueryClient);
const mockedUseRemoveItemsFromPaginatedList = jest.mocked(
  useRemoveItemsFromPaginatedList,
);
const mockedUseUpdateItemInPaginatedList = jest.mocked(
  useUpdateItemInPaginatedList,
);
const mockedUseTreeContext = jest.mocked(useTreeContext);
const mockedGenerateTreeId = jest.mocked(generateTreeId);

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

type QueryClientMock = {
  invalidateQueries: jest.Mock;
  cancelQueries: jest.Mock;
  getQueryData: jest.Mock;
  removeQueries: jest.Mock;
  setQueryData: jest.Mock;
};

describe("useRefreshItems", () => {
  const invalidateQueries = jest.fn();
  const cancelQueries = jest.fn();
  const getQueryData = jest.fn();
  const removeQueries = jest.fn();
  const setQueryData = jest.fn();
  const removeItems = jest.fn();
  const updateItemInList = jest.fn();
  const deleteNode = jest.fn();

  const queryClient: QueryClientMock = {
    invalidateQueries,
    cancelQueries,
    getQueryData,
    removeQueries,
    setQueryData,
  };

  beforeEach(() => {
    invalidateQueries.mockReset();
    cancelQueries.mockReset();
    cancelQueries.mockResolvedValue(undefined);
    getQueryData.mockReset();
    removeQueries.mockReset();
    setQueryData.mockReset();
    removeItems.mockReset();
    updateItemInList.mockReset();
    deleteNode.mockReset();

    mockedUseQueryClient.mockReturnValue(queryClient as never);
    mockedUseRemoveItemsFromPaginatedList.mockReturnValue(removeItems);
    mockedUseUpdateItemInPaginatedList.mockReturnValue(updateItemInList);
    mockedUseTreeContext.mockReturnValue({
      treeData: {
        deleteNode,
      },
    } as never);
    mockedGenerateTreeId.mockReturnValue("favorites-node-1");
  });

  it("computes default vs parent query keys coherently", () => {
    const getQueryKeys = useGetQueryKeyToRefresh();

    expect(getQueryKeys()).toEqual([["items", "infinite"]]);
    expect(getQueryKeys("parent-1")).toEqual([
      ["items", "infinite"],
      ["items", "parent-1", "children"],
    ]);
  });

  it("invalidates every query key returned for a mutation refresh", () => {
    const refresh = useRefreshQueryCacheAfterMutation();

    refresh("parent-1");

    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "infinite"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["items", "parent-1", "children"],
    });
  });

  it("keeps delete mutation callbacks coherent across optimistic remove, rollback and final invalidation", async () => {
    const childrenQuery = ["items", "parent-1", "children"];
    const defaultQueryKey = [["items", "trash"], childrenQuery];

    getQueryData.mockImplementation((queryKey: unknown) => {
      if (JSON.stringify(queryKey) === JSON.stringify(["items", "trash"])) {
        return [buildItem("trash-1")];
      }
      if (JSON.stringify(queryKey) === JSON.stringify(childrenQuery)) {
        return [buildItem("child-1")];
      }
      return undefined;
    });

    const callbacks = useDeleteMutationCallbacks("ignored-parent", defaultQueryKey);
    const context = await callbacks.onMutate(["trash-1", "child-1"]);

    expect(cancelQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "trash"],
    });
    expect(cancelQueries).toHaveBeenNthCalledWith(2, {
      queryKey: childrenQuery,
    });
    expect(removeItems).toHaveBeenNthCalledWith(1, ["items", "trash"], [
      "trash-1",
      "child-1",
    ]);
    expect(removeItems).toHaveBeenNthCalledWith(2, childrenQuery, [
      "trash-1",
      "child-1",
    ]);

    callbacks.onError(undefined, undefined, context);

    expect(setQueryData).toHaveBeenNthCalledWith(1, ["items", "trash"], [
      buildItem("trash-1"),
    ]);
    expect(setQueryData).toHaveBeenNthCalledWith(2, childrenQuery, [
      buildItem("child-1"),
    ]);
    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "trash"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: childrenQuery,
    });

    callbacks.onSuccess();

    expect(invalidateQueries).toHaveBeenNthCalledWith(3, {
      queryKey: ["items", "trash"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(4, {
      queryKey: childrenQuery,
    });
  });

  it("resolves delete mutation query keys from the deleted item ids", async () => {
    getQueryData.mockReturnValue([buildItem("current-folder")]);
    const callbacks = useDeleteMutationCallbacks((itemIds) =>
      itemIds.includes("current-folder") ? "parent-folder" : "current-folder",
    );

    await callbacks.onMutate(["current-folder"]);

    expect(cancelQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "infinite"],
    });
    expect(cancelQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["items", "parent-folder", "children"],
    });

    callbacks.onSuccess(undefined, ["current-folder"]);

    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "infinite"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["items", "parent-folder", "children"],
    });
  });

  it("removes deleted children queries instead of refetching them", async () => {
    getQueryData.mockReturnValue([buildItem("current-folder")]);
    const callbacks = useDeleteMutationCallbacks("current-folder");

    await callbacks.onMutate(["current-folder"]);
    callbacks.onSuccess(undefined, ["current-folder"]);

    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["items", "infinite"],
    });
    expect(removeQueries).toHaveBeenCalledWith({
      queryKey: ["items", "current-folder", "children"],
    });
    expect(invalidateQueries).not.toHaveBeenCalledWith({
      queryKey: ["items", "current-folder", "children"],
    });
  });

  it("keeps confirmed deletions removed when a later item fails in the same batch", async () => {
    const childrenQuery = ["items", "parent-1", "children"];
    const defaultQueryKey = [["items", "trash"], childrenQuery];
    getQueryData.mockReturnValue([buildItem("item-1"), buildItem("item-2")]);

    const callbacks = useDeleteMutationCallbacks("ignored-parent", defaultQueryKey);
    const context = await callbacks.onMutate(["item-1", "item-2"]);

    callbacks.onError(
      new BatchDeleteError({
        completedIds: ["item-1"],
        failedId: "item-2",
        cause: new Error("403"),
      }),
      ["item-1", "item-2"],
      context,
    );

    expect(setQueryData).toHaveBeenNthCalledWith(1, ["items", "trash"], [
      buildItem("item-1"),
      buildItem("item-2"),
    ]);
    expect(removeItems).toHaveBeenNthCalledWith(3, ["items", "trash"], [
      "item-1",
    ]);
    expect(setQueryData).toHaveBeenNthCalledWith(2, childrenQuery, [
      buildItem("item-1"),
      buildItem("item-2"),
    ]);
    expect(removeItems).toHaveBeenNthCalledWith(4, childrenQuery, ["item-1"]);
    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "trash"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: childrenQuery,
    });
  });

  it("refreshes item cache optimistically when a partial update is provided and invalidates otherwise", async () => {
    const refreshItemCache = useRefreshItemCache();
    const partial = { title: "Renamed" };

    await refreshItemCache("item-1", partial);

    expect(updateItemInList).toHaveBeenCalledWith(["items"], "item-1", partial);
    expect(setQueryData).toHaveBeenCalledWith(
      ["items", "item-1"],
      expect.any(Function),
    );
    const updater = setQueryData.mock.calls[0][1] as (old: Item) => Item;
    expect(updater(buildItem("item-1"))).toMatchObject({
      id: "item-1",
      title: "Renamed",
    });

    setQueryData.mockReset();
    await refreshItemCache("item-1", undefined, [["items", "trash"]]);

    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["items", "item-1"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(3, {
      queryKey: ["items", "trash"],
    });
  });

  it("refreshes item plus children cache and targets accesses vs invitations coherently", () => {
    const refreshItemCache = jest.fn();
    const refreshItemCacheSpy = jest
      .spyOn(refreshItemsModule, "useRefreshItemCache")
      .mockReturnValue(refreshItemCache);

    const onSuccessAccessOrInvitation = useOnSuccessAccessOrInvitationMutation();
    onSuccessAccessOrInvitation("item-1", false);
    onSuccessAccessOrInvitation("item-1", true);

    expect(refreshItemCache).toHaveBeenNthCalledWith(1, "item-1");
    expect(refreshItemCache).toHaveBeenNthCalledWith(2, "item-1");
    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "item-1", "children"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["itemAccesses", "item-1"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(3, {
      queryKey: ["items", "item-1", "children"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(4, {
      queryKey: ["itemInvitations", "item-1"],
    });

    refreshItemCacheSpy.mockRestore();
  });

  it("refreshes favorites cache and cleans the root favorite tree node", () => {
    const refreshFavoriteCache = useRefreshFavoriteCache();

    refreshFavoriteCache("item-1", true);

    expect(mockedGenerateTreeId).toHaveBeenCalledWith(
      "item-1",
      "favorites",
      true,
    );
    expect(deleteNode).toHaveBeenCalledWith("favorites-node-1");
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: [
        ["items", "infinite", JSON.stringify({ is_favorite: true })],
        ["items", "item-1"],
      ],
    });
  });
});
