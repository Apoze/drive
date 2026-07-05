import { getDriver } from "@/features/config/Config";
import { BatchOperationError } from "@/features/errors/BatchOperationError";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRemoveItemsFromPaginatedList } from "../hooks/useOptimisticPagination";
import {
  getMyFilesQueryKey,
  getRecentItemsQueryKey,
  getSharedWithMeQueryKey,
} from "@/utils/defaultRoutes";

export const useMoveItems = () => {
  type MoveItemPayload = {
    ids: string[];
    parentId?: string;
    oldParentId?: string;
  };

  const queryClient = useQueryClient();
  const driver = getDriver();

  const removeItems = useRemoveItemsFromPaginatedList();

  const removeMovedItems = (payload: MoveItemPayload, ids: string[]) => {
    if (ids.length === 0) {
      return;
    }

    removeItems(["items", payload.oldParentId], ids);
    removeItems(getMyFilesQueryKey(), ids);
    removeItems(getSharedWithMeQueryKey(), ids);
    removeItems(getRecentItemsQueryKey(), ids);
  };

  const invalidateMoveQueries = (payload: MoveItemPayload) => {
    if (payload.oldParentId) {
      queryClient.invalidateQueries({
        queryKey: ["items", payload.oldParentId],
      });
    }

    if (payload.parentId) {
      queryClient.invalidateQueries({
        queryKey: ["items", payload.parentId],
      });
    }

    queryClient.invalidateQueries({
      queryKey: getMyFilesQueryKey(),
    });
    queryClient.invalidateQueries({
      queryKey: getSharedWithMeQueryKey(),
    });
    queryClient.invalidateQueries({
      queryKey: getRecentItemsQueryKey(),
    });
  };

  return useMutation({
    mutationFn: async (payload: MoveItemPayload) => {
      await driver.moveItems(payload.ids, payload.parentId);
    },
    onMutate: async (payload: MoveItemPayload) => {
      // Cancel any outgoing refetches to avoid overwriting optimistic updates
      await queryClient.cancelQueries({
        queryKey: ["items", payload.oldParentId, "children"],
      });

      await queryClient.cancelQueries({
        queryKey: ["items", payload.parentId, "children"],
      });
    },
    onSuccess: (data, payload: MoveItemPayload) => {
      removeMovedItems(payload, payload.ids);
      invalidateMoveQueries(payload);
    },
    onError: (err, variables) => {
      if (err instanceof BatchOperationError) {
        removeMovedItems(variables, err.completedIds);
      }
      invalidateMoveQueries(variables);
    },
    meta: {
      showErrorOn403: true,
      noGlobalError: true,
    },
  });
};
