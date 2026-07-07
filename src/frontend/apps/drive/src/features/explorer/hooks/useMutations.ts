import { getDriver } from "@/features/config/Config";
import { QueryKey, useMutation, useQueryClient } from "@tanstack/react-query";
import { ItemFilters } from "@/features/drivers/Driver";
import {
  useGlobalExplorer,
  generateTreeId,
} from "../components/GlobalExplorerContext";
import { getParentIdFromPath } from "../utils/utils";
import {
  useAddItemToPaginatedList,
  useRemoveItemsFromPaginatedList,
} from "./useOptimisticPagination";
import { useTreeContext } from "@gouvfr-lasuite/ui-kit";
import {
  useRefreshQueryCacheAfterMutation,
  useDeleteMutationCallbacks,
  useRefreshItemCache,
  useRefreshFavoriteCache,
} from "./useRefreshItems";
import { DefaultRoute } from "@/utils/defaultRoutes";

// ============================================================================
// MUTATIONS
// ============================================================================

const shouldAddCreatedRootItemToQuery = (queryKey: QueryKey) => {
  if (
    !Array.isArray(queryKey) ||
    queryKey[0] !== "items" ||
    queryKey[1] !== "infinite"
  ) {
    return false;
  }

  const rawFilters = queryKey[2];
  if (typeof rawFilters !== "string") {
    return true;
  }

  try {
    const filters = JSON.parse(rawFilters) as ItemFilters;
    return (
      filters.is_favorite !== true &&
      filters.is_creator_me !== false &&
      filters.scope === undefined &&
      filters.workspace === undefined
    );
  } catch {
    return false;
  }
};

const ROOT_CREATE_QUERY_KEYS: QueryKey[] = [
  ["items", "infinite"],
  ["items", "infinite", JSON.stringify({ is_creator_me: true })],
  [
    "items",
    "infinite",
    JSON.stringify({ is_creator_me: true, ordering: "-type,title" }),
  ],
  [
    "items",
    "infinite",
    JSON.stringify({ ordering: "-type,title", is_creator_me: true }),
  ],
];

export const useMutationCreateFile = () => {
  const driver = getDriver();
  const refresh = useRefreshQueryCacheAfterMutation();

  return useMutation({
    mutationFn: async (...payload: Parameters<typeof driver.createFile>) => {
      return driver.createFile(...payload).promise;
    },
    onSuccess: (data, variables) => {
      refresh(variables.parentId);
    },
    meta: {
      showErrorOn403: true,
      noGlobalError: true,
    },
  });
};

export const useMutationCreateOdfDocument = () => {
  const driver = getDriver();
  const refresh = useRefreshQueryCacheAfterMutation();

  return useMutation({
    mutationFn: async (
      ...payload: Parameters<typeof driver.createOdfDocument>
    ) => {
      return driver.createOdfDocument(...payload);
    },
    onSuccess: (_data, variables) => {
      refresh(variables.parentId);
    },
    meta: {
      showErrorOn403: true,
      noGlobalError: true,
    },
  });
};

export const useMutationCreateNewFile = () => {
  const driver = getDriver();
  const refresh = useRefreshQueryCacheAfterMutation();

  return useMutation({
    mutationFn: async (...payload: Parameters<typeof driver.createNewFile>) => {
      return driver.createNewFile(...payload);
    },
    onSuccess: (_data, variables) => {
      refresh(variables.parentId);
    },
    meta: {
      showErrorOn403: true,
      noGlobalError: true,
    },
  });
};

export const useMutationCreateFileFromTemplate = () => {
  const driver = getDriver();
  const refresh = useRefreshQueryCacheAfterMutation();
  return useMutation({
    mutationFn: async (
      ...payload: Parameters<typeof driver.createFileFromTemplate>
    ) => {
      return driver.createFileFromTemplate(...payload);
    },
    onSuccess: (data, variables) => {
      refresh(variables.parentId);
    },
    meta: {
      showErrorOn403: true,
    },
  });
};

export const useMutationDeleteItems = () => {
  const driver = getDriver();
  const { item } = useGlobalExplorer();
  const currentItemId = item?.originalId ?? item?.id;

  const mutationCallbacks = useDeleteMutationCallbacks((itemIds) =>
    currentItemId && itemIds.includes(currentItemId)
      ? getParentIdFromPath(item?.path)
      : currentItemId,
  );

  return useMutation({
    mutationFn: async (...payload: Parameters<typeof driver.deleteItems>) => {
      await driver.deleteItems(...payload);
    },
    ...mutationCallbacks,
    meta: {
      showErrorOn403: true,
      noGlobalError: true,
    },
  });
};

export const useMutationDuplicateItem = () => {
  const driver = getDriver();
  const { item } = useGlobalExplorer();
  const refresh = useRefreshQueryCacheAfterMutation();

  return useMutation({
    mutationFn: async (...payload: Parameters<typeof driver.duplicateItem>) => {
      return driver.duplicateItem(...payload);
    },
    onSuccess: () => {
      refresh(item?.originalId ?? item?.id);
    },
    meta: {
      showErrorOn403: true,
      noGlobalError: true,
    },
  });
};

export const useMutationConvertItem = () => {
  const driver = getDriver();
  const { item } = useGlobalExplorer();
  const refresh = useRefreshQueryCacheAfterMutation();
  const addItemToTopOfPaginatedList = useAddItemToPaginatedList();

  return useMutation({
    mutationFn: (itemId: string) => {
      return driver.convertItem(itemId);
    },
    onSuccess: (convertedItem) => {
      const currentItemId = item?.originalId ?? item?.id;
      if (currentItemId) {
        addItemToTopOfPaginatedList(
          ["items", currentItemId, "children"],
          convertedItem,
        );
      }
      refresh(currentItemId);
    },
    meta: {
      showErrorOn403: true,
      noGlobalError: true,
    },
  });
};

export const useMutationHardDeleteItems = () => {
  const driver = getDriver();
  const mutationCallbacks = useDeleteMutationCallbacks(undefined, [
    ["items", "trash"],
  ]);

  return useMutation({
    mutationFn: async (
      ...payload: Parameters<typeof driver.hardDeleteItems>
    ) => {
      await driver.hardDeleteItems(...payload);
    },
    ...mutationCallbacks,
    meta: {
      showErrorOn403: true,
      noGlobalError: true,
    },
  });
};

export const useMutationRenameItem = () => {
  const driver = getDriver();
  const refreshItemCache = useRefreshItemCache();

  return useMutation({
    mutationFn: async (...payload: Parameters<typeof driver.updateItem>) => {
      await driver.updateItem(...payload);
    },
    onMutate: async (...payload: Parameters<typeof driver.updateItem>) => {
      if (!payload[0].id) {
        return;
      }
      await refreshItemCache(payload[0].id!, { title: payload[0].title });
    },
    onError: (_error, variables) => {
      if (!variables.id) {
        return;
      }

      refreshItemCache(variables.id);
    },

    onSuccess: (_, itemUpdated) => {
      if (!itemUpdated?.id) {
        return;
      }
      refreshItemCache(itemUpdated.id, itemUpdated);
    },
  });
};

export const useMutationCreateFolder = () => {
  const driver = getDriver();
  const addItemToTopOfPaginatedList = useAddItemToPaginatedList();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (...payload: Parameters<typeof driver.createFolder>) => {
      return driver.createFolder(...payload);
    },
    onSuccess: (data, variables) => {
      if (variables.parentId) {
        const queryKey = ["items", variables.parentId, "children"];
        addItemToTopOfPaginatedList(queryKey, data);
        queryClient.invalidateQueries({
          queryKey,
        });
        return;
      }

      ROOT_CREATE_QUERY_KEYS.forEach((queryKey) => {
        addItemToTopOfPaginatedList(queryKey, data);
      });
      const handledRootQueryKeys = new Set(
        ROOT_CREATE_QUERY_KEYS.map((queryKey) => JSON.stringify(queryKey)),
      );
      queryClient
        .getQueriesData({ queryKey: ["items", "infinite"] })
        .forEach(([queryKey]) => {
          const queryKeySignature = JSON.stringify(queryKey);
          if (
            !handledRootQueryKeys.has(queryKeySignature) &&
            shouldAddCreatedRootItemToQuery(queryKey)
          ) {
            addItemToTopOfPaginatedList(queryKey, data);
          }
        });
      queryClient.invalidateQueries({
        queryKey: ["items"],
      });
    },
  });
};

export const useMutationUpdateLinkConfiguration = () => {
  const driver = getDriver();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      ...payload: Parameters<typeof driver.updateLinkConfiguration>
    ) => {
      await driver.updateLinkConfiguration(...payload);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["items", variables.itemId],
      });

      queryClient.invalidateQueries({
        queryKey: ["itemAccesses"],
      });
    },
  });
};

export const useMutationRestoreItems = () => {
  const driver = getDriver();
  const mutationCallbacks = useDeleteMutationCallbacks(undefined, [
    ["items", "trash"],
  ]);
  return useMutation({
    mutationFn: async (...payload: Parameters<typeof driver.restoreItems>) => {
      await driver.restoreItems(...payload);
    },
    ...mutationCallbacks,
    meta: {
      showErrorOn403: true,
      noGlobalError: true,
    },
  });
};

export const useMutationCreateWorskpace = () => {
  const queryClient = useQueryClient();
  const driver = getDriver();

  return useMutation({
    mutationFn: (...payload: Parameters<typeof driver.createWorkspace>) => {
      return driver.createWorkspace(...payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["items"],
      });
    },
  });
};

// TODO: Make optimistic once the tree is implemented
export const useMutationUpdateWorkspace = () => {
  const driver = getDriver();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (
      ...payload: Parameters<typeof driver.updateWorkspace>
    ) => {
      await driver.updateWorkspace(...payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["items"],
      });
    },
  });
};

export const useMutationCreateFavoriteItem = () => {
  const driver = getDriver();

  const refreshFavoriteCache = useRefreshFavoriteCache();
  const refreshItemCache = useRefreshItemCache();

  return useMutation({
    mutationFn: (...payload: Parameters<typeof driver.createFavoriteItem>) => {
      return driver.createFavoriteItem(...payload);
    },
    onSuccess: (_, itemId: string) => {
      refreshFavoriteCache(itemId, true);
      refreshItemCache(itemId, { is_favorite: true });
    },
  });
};

export const useMutationDeleteFavoriteItem = () => {
  const driver = getDriver();
  const treeContext = useTreeContext();
  const removeItems = useRemoveItemsFromPaginatedList();
  const refreshFavoriteCache = useRefreshFavoriteCache();
  const refreshItemCache = useRefreshItemCache();
  return useMutation({
    mutationFn: (...payload: Parameters<typeof driver.deleteFavoriteItem>) => {
      return driver.deleteFavoriteItem(...payload);
    },
    onSuccess: (_data, itemId: string) => {
      // Only delete the root favorite node (directly under favorites)
      // Children of opened favorite folders should remain visible
      const rootFavoriteTreeId = generateTreeId(
        itemId,
        DefaultRoute.FAVORITES,
        true,
      );
      treeContext?.treeData.deleteNode(rootFavoriteTreeId);
      removeItems(
        ["items", "infinite", JSON.stringify({ is_favorite: true })],
        [itemId],
      );
      refreshItemCache(itemId, { is_favorite: false });
      refreshFavoriteCache(itemId, false);
    },
  });
};
