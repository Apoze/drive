import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { ItemFilters } from "@/features/drivers/Driver";
import { useMemo, useState } from "react";
import { useInfiniteRecentItems } from "@/features/explorer/hooks/useInfiniteItems";
import { AppExplorer } from "@/features/explorer/components/app-view/AppExplorer";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";
import { ItemType } from "@/features/drivers/types";
export default function RecentPage() {
  const [filters, setFilters] = useState<ItemFilters>({
    type: ItemType.FILE,
  });

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteRecentItems(filters);

  // Flatten all pages into a single array of items
  const itemChildren = useMemo(() => {
    return data?.pages.flatMap((page) => page.children) ?? [];
  }, [data]);

  useDefaultRoute(DefaultRoute.RECENT);

  return (
    <AppExplorer
      childrenItems={itemChildren}
      filters={filters}
      onFiltersChange={setFilters}
      hasNextPage={hasNextPage}
      showFilters={true}
      isFetchingNextPage={isFetchingNextPage}
      fetchNextPage={fetchNextPage}
      isLoading={isLoading}
    />
  );
}

RecentPage.getLayout = getGlobalExplorerLayout;
