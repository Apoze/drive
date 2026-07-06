import { DefaultRoute } from "@/utils/defaultRoutes";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  type Item,
} from "@/features/drivers/types";
import { getDriver } from "@/features/config/Config";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTreeContext } from "@gouvfr-lasuite/ui-kit";
import {
  generateTreeId,
  useGlobalExplorer,
} from "../../components/GlobalExplorerContext";
import {
  useAddItemToPaginatedList,
  useRemoveItemsFromPaginatedList,
} from "../useOptimisticPagination";
import {
  useDeleteMutationCallbacks,
  useRefreshFavoriteCache,
  useRefreshItemCache,
  useRefreshQueryCacheAfterMutation,
} from "../useRefreshItems";
import {
  useMutationCreateFavoriteItem,
  useMutationCreateFile,
  useMutationCreateFileFromTemplate,
  useMutationCreateFolder,
  useMutationCreateNewFile,
  useMutationCreateOdfDocument,
  useMutationCreateWorskpace,
  useMutationDeleteFavoriteItem,
  useMutationDeleteItems,
  useMutationHardDeleteItems,
  useMutationRenameItem,
  useMutationRestoreItems,
  useMutationUpdateWorkspace,
} from "../useMutations";

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@tanstack/react-query", () => ({
  useMutation: jest.fn((config) => config),
  useQueryClient: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  useTreeContext: jest.fn(),
}));

jest.mock("../../components/GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
  generateTreeId: jest.fn(),
}));

jest.mock("../useOptimisticPagination", () => ({
  useAddItemToPaginatedList: jest.fn(),
  useRemoveItemsFromPaginatedList: jest.fn(),
}));

jest.mock("../useRefreshItems", () => ({
  useRefreshQueryCacheAfterMutation: jest.fn(),
  useDeleteMutationCallbacks: jest.fn(),
  useRefreshItemCache: jest.fn(),
  useRefreshFavoriteCache: jest.fn(),
}));

const mockedGetDriver = jest.mocked(getDriver);
const mockedUseMutation = jest.mocked(useMutation);
const mockedUseQueryClient = jest.mocked(useQueryClient);
const mockedUseTreeContext = jest.mocked(useTreeContext);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedGenerateTreeId = jest.mocked(generateTreeId);
const mockedUseAddItemToPaginatedList = jest.mocked(useAddItemToPaginatedList);
const mockedUseRemoveItemsFromPaginatedList = jest.mocked(
  useRemoveItemsFromPaginatedList,
);
const mockedUseRefreshQueryCacheAfterMutation = jest.mocked(
  useRefreshQueryCacheAfterMutation,
);
const mockedUseDeleteMutationCallbacks = jest.mocked(useDeleteMutationCallbacks);
const mockedUseRefreshItemCache = jest.mocked(useRefreshItemCache);
const mockedUseRefreshFavoriteCache = jest.mocked(useRefreshFavoriteCache);

type MutationConfig<TVariables, TData = unknown, TContext = unknown> = {
  mutationFn: (variables: TVariables) => Promise<TData> | TData;
  onSuccess?: (data: TData, variables: TVariables) => void;
  onMutate?: (variables: TVariables) => Promise<TContext> | TContext;
  onError?: (error: unknown, variables: TVariables, context: TContext) => void;
  meta?: Record<string, unknown>;
};

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

describe("useMutations", () => {
  const invalidateQueries = jest.fn();
  const cancelQueries = jest.fn();
  const getQueryData = jest.fn();
  const getQueriesData = jest.fn();
  const setQueryData = jest.fn();
  const refresh = jest.fn();
  const refreshItemCache = jest.fn();
  const refreshFavoriteCache = jest.fn();
  const addItemToTopOfPaginatedList = jest.fn();
  const removeItems = jest.fn();
  const deleteNode = jest.fn();

  const deleteMutationCallbacks = {
    onMutate: jest.fn(),
    onError: jest.fn(),
    onSuccess: jest.fn(),
  };

  const driver = {
    createFile: jest.fn(),
    createOdfDocument: jest.fn(),
    createNewFile: jest.fn(),
    createFileFromTemplate: jest.fn(),
    deleteItems: jest.fn(),
    hardDeleteItems: jest.fn(),
    updateItem: jest.fn(),
    createFolder: jest.fn(),
    restoreItems: jest.fn(),
    createWorkspace: jest.fn(),
    updateWorkspace: jest.fn(),
    createFavoriteItem: jest.fn(),
    deleteFavoriteItem: jest.fn(),
  };

  beforeEach(() => {
    invalidateQueries.mockReset();
    cancelQueries.mockReset();
    cancelQueries.mockResolvedValue(undefined);
    getQueryData.mockReset();
    getQueriesData.mockReset();
    getQueriesData.mockReturnValue([]);
    setQueryData.mockReset();
    refresh.mockReset();
    refreshItemCache.mockReset();
    refreshFavoriteCache.mockReset();
    addItemToTopOfPaginatedList.mockReset();
    removeItems.mockReset();
    deleteNode.mockReset();
    mockedUseMutation.mockClear();
    Object.values(deleteMutationCallbacks).forEach((fn) => fn.mockReset());
    Object.values(driver).forEach((fn) => fn.mockReset());

    mockedGetDriver.mockReturnValue(driver as never);
    mockedUseQueryClient.mockReturnValue({
      invalidateQueries,
      cancelQueries,
      getQueryData,
      getQueriesData,
      setQueryData,
    } as never);
    mockedUseRefreshQueryCacheAfterMutation.mockReturnValue(refresh);
    mockedUseRefreshItemCache.mockReturnValue(refreshItemCache);
    mockedUseRefreshFavoriteCache.mockReturnValue(refreshFavoriteCache);
    mockedUseAddItemToPaginatedList.mockReturnValue(addItemToTopOfPaginatedList);
    mockedUseRemoveItemsFromPaginatedList.mockReturnValue(removeItems);
    mockedUseDeleteMutationCallbacks.mockReturnValue(deleteMutationCallbacks);
    mockedUseTreeContext.mockReturnValue({
      treeData: { deleteNode },
    } as never);
    mockedUseGlobalExplorer.mockReturnValue({
      item: { id: "item-current", originalId: "item-original" },
    } as never);
    mockedGenerateTreeId.mockReturnValue("favorites-node-1");
  });

  it.each([
    [
      "useMutationCreateFile",
      useMutationCreateFile,
      "createFile",
      { parentId: "parent-1", title: "file.txt" },
      { showErrorOn403: true, noGlobalError: true },
    ],
    [
      "useMutationCreateOdfDocument",
      useMutationCreateOdfDocument,
      "createOdfDocument",
      { parentId: "parent-2", title: "doc.odt" },
      { showErrorOn403: true, noGlobalError: true },
    ],
    [
      "useMutationCreateNewFile",
      useMutationCreateNewFile,
      "createNewFile",
      { parentId: "parent-3", title: "new.docx" },
      { showErrorOn403: true, noGlobalError: true },
    ],
    [
      "useMutationCreateFileFromTemplate",
      useMutationCreateFileFromTemplate,
      "createFileFromTemplate",
      { parentId: "parent-4", templateId: "template-1" },
      { showErrorOn403: true },
    ],
  ])("%s wires the driver and refreshes the parent query", async (_label, hookFactory, driverMethod, variables, meta) => {
    (driver[driverMethod as keyof typeof driver] as jest.Mock).mockResolvedValue("created");

    const mutation = hookFactory() as unknown as MutationConfig<
      typeof variables,
      unknown
    >;

    await mutation.mutationFn(variables);
    mutation.onSuccess?.("created", variables);

    expect(driver[driverMethod as keyof typeof driver]).toHaveBeenCalledWith(variables);
    expect(refresh).toHaveBeenCalledWith(variables.parentId);
    expect(mutation.meta).toEqual(meta);
  });

  it("reuses delete mutation callbacks for delete items with the explorer current parent", async () => {
    driver.deleteItems.mockResolvedValue(undefined);

    const mutation =
      useMutationDeleteItems() as unknown as MutationConfig<string[]>;

    await mutation.mutationFn(["item-1"]);

    expect(mockedUseDeleteMutationCallbacks).toHaveBeenCalledWith("item-original");
    expect(driver.deleteItems).toHaveBeenCalledWith(["item-1"]);
    expect(mutation.onMutate).toBe(deleteMutationCallbacks.onMutate);
    expect(mutation.onError).toBe(deleteMutationCallbacks.onError);
    expect(mutation.onSuccess).toBe(deleteMutationCallbacks.onSuccess);
    expect(mutation.meta).toEqual({
      showErrorOn403: true,
      noGlobalError: true,
    });
  });

  it("reuses delete mutation callbacks for hard delete items with the trash key", async () => {
    driver.hardDeleteItems.mockResolvedValue(undefined);

    const mutation =
      useMutationHardDeleteItems() as unknown as MutationConfig<string[]>;

    await mutation.mutationFn(["item-1"]);

    expect(mockedUseDeleteMutationCallbacks).toHaveBeenCalledWith(undefined, [
      ["items", "trash"],
    ]);
    expect(driver.hardDeleteItems).toHaveBeenCalledWith(["item-1"]);
  });

  it("keeps rename optimistic refresh and rollback coherent", async () => {
    driver.updateItem.mockResolvedValue(undefined);

    const mutation = useMutationRenameItem() as unknown as MutationConfig<{
      id?: string;
      title: string;
      is_favorite?: boolean;
    }>;

    await mutation.mutationFn({ id: "item-1", title: "Renamed" });
    await mutation.onMutate?.({ id: "item-1", title: "Renamed" });
    mutation.onError?.(undefined, { id: "item-1", title: "Renamed" }, undefined);
    mutation.onSuccess?.(undefined, {
      id: "item-1",
      title: "Renamed",
      is_favorite: true,
    });
    await mutation.onMutate?.({ title: "No id" });
    mutation.onError?.(undefined, { title: "No id" }, undefined);

    expect(driver.updateItem).toHaveBeenCalledWith({
      id: "item-1",
      title: "Renamed",
    });
    expect(refreshItemCache).toHaveBeenNthCalledWith(1, "item-1", {
      title: "Renamed",
    });
    expect(refreshItemCache).toHaveBeenNthCalledWith(2, "item-1");
    expect(refreshItemCache).toHaveBeenNthCalledWith(3, "item-1", {
      id: "item-1",
      title: "Renamed",
      is_favorite: true,
    });
    expect(refreshItemCache).toHaveBeenCalledTimes(3);
  });

  it("adds a created folder to the top of the right query and invalidates it", async () => {
    const createdFolder = buildItem("folder-1", { type: ItemType.FOLDER });
    driver.createFolder.mockResolvedValue(createdFolder);

    const mutation = useMutationCreateFolder() as unknown as MutationConfig<
      {
        parentId?: string;
        title: string;
      },
      Item
    >;

    await mutation.mutationFn({ parentId: "parent-1", title: "Folder" });
    mutation.onSuccess?.(createdFolder, { parentId: "parent-1", title: "Folder" });
    getQueriesData.mockReturnValue([
      [["items", "infinite"], {}],
      [
        [
          "items",
          "infinite",
          JSON.stringify({ is_creator_me: true, ordering: "-type,title" }),
        ],
        {},
      ],
      [
        [
          "items",
          "infinite",
          JSON.stringify({ is_creator_me: true, ordering: "title" }),
        ],
        {},
      ],
      [["items", "infinite", JSON.stringify({ is_favorite: true })], {}],
    ]);
    mutation.onSuccess?.(createdFolder, { title: "Root folder" });

    expect(addItemToTopOfPaginatedList).toHaveBeenNthCalledWith(
      1,
      ["items", "parent-1", "children"],
      createdFolder,
    );
    expect(addItemToTopOfPaginatedList).toHaveBeenNthCalledWith(
      2,
      ["items", "infinite"],
      createdFolder,
    );
    expect(addItemToTopOfPaginatedList).toHaveBeenNthCalledWith(
      3,
      ["items", "infinite", JSON.stringify({ is_creator_me: true })],
      createdFolder,
    );
    expect(addItemToTopOfPaginatedList).toHaveBeenNthCalledWith(
      4,
      [
        "items",
        "infinite",
        JSON.stringify({ is_creator_me: true, ordering: "-type,title" }),
      ],
      createdFolder,
    );
    expect(addItemToTopOfPaginatedList).toHaveBeenNthCalledWith(
      5,
      [
        "items",
        "infinite",
        JSON.stringify({ ordering: "-type,title", is_creator_me: true }),
      ],
      createdFolder,
    );
    expect(addItemToTopOfPaginatedList).toHaveBeenNthCalledWith(
      6,
      [
        "items",
        "infinite",
        JSON.stringify({ is_creator_me: true, ordering: "title" }),
      ],
      createdFolder,
    );
    expect(addItemToTopOfPaginatedList).toHaveBeenCalledTimes(6);
    expect(getQueriesData).toHaveBeenCalledWith({
      queryKey: ["items", "infinite"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "parent-1", "children"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["items", "infinite"],
    });
  });

  it("reuses delete mutation callbacks for restore items with the trash key", async () => {
    driver.restoreItems.mockResolvedValue(undefined);
    const mutation =
      useMutationRestoreItems() as unknown as MutationConfig<string[]>;

    await mutation.mutationFn(["trash-1"]);

    expect(driver.restoreItems).toHaveBeenCalledWith(["trash-1"]);
    expect(mockedUseDeleteMutationCallbacks).toHaveBeenCalledWith(undefined, [
      ["items", "trash"],
    ]);
    expect(mutation.onMutate).toBe(deleteMutationCallbacks.onMutate);
    expect(mutation.onError).toBe(deleteMutationCallbacks.onError);
    expect(mutation.onSuccess).toBe(deleteMutationCallbacks.onSuccess);
    expect(mutation.meta).toEqual({
      showErrorOn403: true,
      noGlobalError: true,
    });
  });

  it("invalidates items after workspace create and update", async () => {
    driver.createWorkspace.mockResolvedValue(undefined);
    driver.updateWorkspace.mockResolvedValue(undefined);

    const createWorkspace =
      useMutationCreateWorskpace() as unknown as MutationConfig<{
        title: string;
      }>;
    const updateWorkspace =
      useMutationUpdateWorkspace() as unknown as MutationConfig<{
        id: string;
        title: string;
      }>;

    await createWorkspace.mutationFn({ title: "Workspace" });
    createWorkspace.onSuccess?.(undefined, { title: "Workspace" });
    await updateWorkspace.mutationFn({ id: "workspace-1", title: "Renamed" });
    updateWorkspace.onSuccess?.(undefined, { id: "workspace-1", title: "Renamed" });

    expect(driver.createWorkspace).toHaveBeenCalledWith({ title: "Workspace" });
    expect(driver.updateWorkspace).toHaveBeenCalledWith({
      id: "workspace-1",
      title: "Renamed",
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["items"],
    });
  });

  it("refreshes favorite creation and deletion coherently", async () => {
    driver.createFavoriteItem.mockResolvedValue(undefined);
    driver.deleteFavoriteItem.mockResolvedValue(undefined);

    const createFavorite =
      useMutationCreateFavoriteItem() as unknown as MutationConfig<string>;
    const deleteFavorite =
      useMutationDeleteFavoriteItem() as unknown as MutationConfig<string>;

    await createFavorite.mutationFn("item-1");
    createFavorite.onSuccess?.(undefined, "item-1");
    await deleteFavorite.mutationFn("item-1");
    deleteFavorite.onSuccess?.(undefined, "item-1");

    expect(driver.createFavoriteItem).toHaveBeenCalledWith("item-1");
    expect(driver.deleteFavoriteItem).toHaveBeenCalledWith("item-1");
    expect(refreshFavoriteCache).toHaveBeenNthCalledWith(1, "item-1", true);
    expect(refreshItemCache).toHaveBeenNthCalledWith(1, "item-1", {
      is_favorite: true,
    });
    expect(mockedGenerateTreeId).toHaveBeenCalledWith(
      "item-1",
      DefaultRoute.FAVORITES,
      true,
    );
    expect(deleteNode).toHaveBeenCalledWith("favorites-node-1");
    expect(removeItems).toHaveBeenCalledWith(
      ["items", "infinite", JSON.stringify({ is_favorite: true })],
      ["item-1"],
    );
    expect(refreshItemCache).toHaveBeenNthCalledWith(2, "item-1", {
      is_favorite: false,
    });
    expect(refreshFavoriteCache).toHaveBeenNthCalledWith(2, "item-1", false);
  });
});
