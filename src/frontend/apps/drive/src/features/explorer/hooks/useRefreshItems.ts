import { useQueryClient, QueryKey } from "@tanstack/react-query";
import { Item } from "@/features/drivers/types";
import {
  useRemoveItemsFromPaginatedList,
  useUpdateItemInPaginatedList,
} from "./useOptimisticPagination";
import { useTreeContext } from "@gouvfr-lasuite/ui-kit";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { generateTreeId } from "../components/GlobalExplorerContext";
import { BatchOperationError } from "@/features/errors/BatchOperationError";

export const useGetQueryKeyToRefresh = () => {
  return (parentId?: string) => {
    const queryKeys = [["items", "infinite"]];
    if (parentId) {
      queryKeys.push(["items", parentId, "children"]);
    }
    // let queryKey = parentId ? ["items", parentId, "children"] : [];
    // if (queryKeyForRoute.length > 0) {
    //   queryKey = queryKeyForRoute;
    // }
    return queryKeys;
  };
};

export const useRefreshQueryCacheAfterMutation = () => {
  const queryClient = useQueryClient();
  const getQueryKey = useGetQueryKeyToRefresh();

  return (parentId?: string) => {
    const queryKey = getQueryKey(parentId);

    for (const key of queryKey) {
      queryClient.invalidateQueries({
        queryKey: key,
      });
    }
  };
};

export const useDeleteMutationCallbacks = (
  parentId?: string | ((itemIds: string[]) => string | undefined),
  defaultQueryKey?: string[][],
) => {
  const queryClient = useQueryClient();
  const getQueryKey = useGetQueryKeyToRefresh();
  const removeItems = useRemoveItemsFromPaginatedList();
  const getQueryKeys = (itemIds: string[] = []) =>
    defaultQueryKey ??
    getQueryKey(
      typeof parentId === "function" ? parentId(itemIds) : parentId,
    );

  const onMutate = async (itemIds: string[]) => {
    const returnPreviousItems: Map<string[], Item[]> = new Map();
    const queryKeys = getQueryKeys(itemIds);
    queryKeys.forEach(async (key) => {
      await queryClient.cancelQueries({
        queryKey: key,
      });
      const previousItems = queryClient.getQueryData<Item[]>(key);
      returnPreviousItems.set(key, previousItems ?? []);
      removeItems(key, itemIds);
    });

    return { previousItems: returnPreviousItems };
  };

  const onError = (_err: unknown, _variables: unknown, context: unknown) => {
    const returnPreviousItems = context as {
      previousItems: Map<string[], Item[]>;
    };
    const error = _err instanceof BatchOperationError ? _err : null;
    returnPreviousItems.previousItems.forEach((previousItems, key) => {
      queryClient.setQueryData(key, previousItems);
      if (error?.completedIds.length) {
        removeItems(key, error.completedIds);
      }
      queryClient.invalidateQueries({
        queryKey: key,
      });
    });
  };

  const onSuccess = (_data?: unknown, itemIds: string[] = []) => {
    const queryKeys = getQueryKeys(itemIds);
    queryKeys.forEach((key) => {
      queryClient.invalidateQueries({
        queryKey: key,
      });
    });
  };

  return { onMutate, onError, onSuccess };
};

// Explanation:
// The function below is used to refresh the cache for certain queries after a mutation (creation, deletion, update)
// on items/files in the explorer. It takes as an argument the id of the parent whose list of children needs to be refreshed.
// It uses the QueryClient from react-query to force reloading/invalidating queries associated with the parent key:
// - This prevents the UI from becoming out of sync with the backend state after a mutation.
export const useRefreshItemCache = () => {
  const queryClient = useQueryClient();

  const updateItemInPaginatedList = useUpdateItemInPaginatedList();
  return async (
    itemId: string,
    partialUpdate?: Partial<Item>,
    moreQueriesToInvalidate?: QueryKey[],
  ) => {
    if (partialUpdate) {
      updateItemInPaginatedList(["items"], itemId, partialUpdate);
      queryClient.setQueryData(["items", itemId], (old: Item) => {
        return {
          ...old,
          ...partialUpdate,
        };
      });
    } else {
      queryClient.invalidateQueries({
        queryKey: ["items"],
      });
      queryClient.invalidateQueries({
        queryKey: ["items", itemId],
      });
      moreQueriesToInvalidate?.forEach((queryKey) => {
        queryClient.invalidateQueries({
          queryKey,
        });
      });
    }
  };
};

export const useOnSuccessAccessOrInvitationMutation = () => {
  const queryClient = useQueryClient();
  const refreshItemCache = useRefreshItemCache();
  return (itemId: string, isInvitation: boolean = false) => {
    refreshItemCache(itemId);
    queryClient.invalidateQueries({
      queryKey: ["items", itemId, "children"],
    });

    if (isInvitation) {
      queryClient.invalidateQueries({
        queryKey: ["itemInvitations", itemId],
      });
    } else {
      queryClient.invalidateQueries({
        queryKey: ["itemAccesses", itemId],
      });
    }
  };
};

export const useRefreshFavoriteCache = () => {
  const queryClient = useQueryClient();
  const treeContext = useTreeContext();

  return (itemId: string, isFavorite: boolean) => {
    const moreQueriesToInvalidate: QueryKey[] = [
      ["items", "infinite", JSON.stringify({ is_favorite: isFavorite })],
      ["items", itemId],
    ];

    const rootFavoriteTreeId = generateTreeId(
      itemId,
      DefaultRoute.FAVORITES,
      true,
    );
    treeContext?.treeData.deleteNode(rootFavoriteTreeId);

    queryClient.invalidateQueries({
      queryKey: moreQueriesToInvalidate,
    });
  };
};
