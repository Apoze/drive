import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { ItemsBrowseExplorer } from "@/features/explorer/components/items-browse/ItemsBrowseExplorer";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";
import { ItemType } from "@/features/drivers/types";
import { useConfig } from "@/features/config/ConfigProvider";
import { ResourceCollection } from "@/features/storage/ResourceCollection";

export default function RecentPage() {
  useDefaultRoute(DefaultRoute.RECENT);
  const { config } = useConfig();
  if (config.STORAGE_UNIFIED_ENABLED)
    return <ResourceCollection mode="recent" />;

  return (
    <ItemsBrowseExplorer
      kind="recent"
      defaultFilters={{ type: ItemType.FILE }}
      showFilters
      viewConfigKey={DefaultRoute.RECENT}
    />
  );
}

RecentPage.getLayout = getGlobalExplorerLayout;
