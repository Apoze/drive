import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { ItemsBrowseExplorer } from "@/features/explorer/components/items-browse/ItemsBrowseExplorer";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";
import { ItemType } from "@/features/drivers/types";

export default function RecentPage() {
  useDefaultRoute(DefaultRoute.RECENT);

  return (
    <ItemsBrowseExplorer
      kind="recent"
      defaultFilters={{ type: ItemType.FILE }}
      showFilters
    />
  );
}

RecentPage.getLayout = getGlobalExplorerLayout;
