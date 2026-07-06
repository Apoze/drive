import { getDriver } from "@/features/config/Config";
import { Item, ItemUploadState } from "@/features/drivers/types";
import { useQueries } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";
import { useRefreshItemCache } from "./useRefreshItems";

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 10 * 60 * 1000;

export const useDuplicatingItemsPoller = (items: Item[]) => {
  const refreshItemCache = useRefreshItemCache();
  const startTimesRef = useRef<Map<string, number>>(new Map());
  const duplicatingItems = useMemo(
    () =>
      items.filter((item) => item.upload_state === ItemUploadState.DUPLICATING),
    [items],
  );

  useEffect(() => {
    duplicatingItems.forEach((item) => {
      if (!startTimesRef.current.has(item.id)) {
        startTimesRef.current.set(item.id, Date.now());
      }
    });

    const duplicatingIds = new Set(duplicatingItems.map((item) => item.id));
    Array.from(startTimesRef.current.keys()).forEach((id) => {
      if (!duplicatingIds.has(id)) {
        startTimesRef.current.delete(id);
      }
    });
  }, [duplicatingItems]);

  useQueries({
    queries: duplicatingItems.map((item) => ({
      queryKey: ["items", item.id, "duplicate-poll"],
      queryFn: async () => {
        const updatedItem = await getDriver().getItem(item.id);
        if (updatedItem.upload_state !== ItemUploadState.DUPLICATING) {
          await refreshItemCache(item.id, updatedItem);
        }
        return updatedItem;
      },
      refetchInterval: (query: { state: { data: Item | undefined } }) => {
        const data = query.state.data;
        if (data && data.upload_state !== ItemUploadState.DUPLICATING) {
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
