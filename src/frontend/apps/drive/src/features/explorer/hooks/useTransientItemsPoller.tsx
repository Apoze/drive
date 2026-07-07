import { useMemo, useEffect, useRef } from "react";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { APIError } from "@/features/api/APIError";
import { getDriver } from "@/features/config/Config";
import {
  Item,
  ItemUploadState,
  POLLED_UPLOAD_STATES,
} from "@/features/drivers/types";
import { useRefreshItemCache } from "./useRefreshItems";
import { useRemoveItemsFromPaginatedList } from "./useOptimisticPagination";
import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";
import { useTranslation } from "react-i18next";

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 10 * 60 * 1000;

export const useTransientItemsPoller = (items: Item[]) => {
  const refreshItemCache = useRefreshItemCache();
  const removeItems = useRemoveItemsFromPaginatedList();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const startTimesRef = useRef<Map<string, number>>(new Map());
  const failedToastShownRef = useRef<Set<string>>(new Set());

  const transientItems = useMemo(
    () => items.filter((item) => POLLED_UPLOAD_STATES.includes(item.upload_state)),
    [items],
  );

  useEffect(() => {
    transientItems.forEach((item) => {
      if (!startTimesRef.current.has(item.id)) {
        startTimesRef.current.set(item.id, Date.now());
      }
    });

    const transientIds = new Set(transientItems.map((item) => item.id));
    Array.from(startTimesRef.current.keys()).forEach((id) => {
      if (!transientIds.has(id)) {
        startTimesRef.current.delete(id);
      }
    });
  }, [transientItems]);

  useQueries({
    queries: transientItems.map((item) => ({
      queryKey: ["items", item.id, "transient-poll"],
      queryFn: async (): Promise<Item | null> => {
        try {
          const updatedItem = await getDriver().getItem(item.id);
          if (!POLLED_UPLOAD_STATES.includes(updatedItem.upload_state)) {
            await refreshItemCache(item.id, updatedItem);
          }
          return updatedItem;
        } catch (error) {
          if (error instanceof APIError && error.code === 404) {
            removeItems(["items"], [item.id]);
            queryClient.removeQueries({ queryKey: ["items", item.id] });
            if (
              item.upload_state === ItemUploadState.CONVERTING &&
              !failedToastShownRef.current.has(item.id)
            ) {
              failedToastShownRef.current.add(item.id);
              addToast(
                <ToasterItem type="error">
                  {t("explorer.actions.convert.modal.error")}
                </ToasterItem>,
              );
            }
            return null;
          }
          throw error;
        }
      },
      refetchInterval: (query: { state: { data: Item | null | undefined } }) => {
        const data = query.state.data;
        if (data === null) {
          return false;
        }
        if (data && !POLLED_UPLOAD_STATES.includes(data.upload_state)) {
          return false;
        }
        const startedAt = startTimesRef.current.get(item.id) ?? Date.now();
        return Date.now() - startedAt < POLL_TIMEOUT_MS
          ? POLL_INTERVAL_MS
          : false;
      },
    })),
  });
};
