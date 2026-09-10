import React from "react";
import WorkspacesExplorer from "@/features/explorer/components/workspaces-explorer/WorkspacesExplorer";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { useConfig } from "@/features/config/ConfigProvider";
import { ResourceCollection } from "@/features/storage/ResourceCollection";

export default function FavoritesPage() {
  useDefaultRoute(DefaultRoute.FAVORITES);
  const { config } = useConfig();
  if (config.STORAGE_UNIFIED_ENABLED)
    return <ResourceCollection mode="favorites" />;
  return (
    <WorkspacesExplorer
      defaultFilters={{ is_favorite: true }}
      viewConfigKey={DefaultRoute.FAVORITES}
    />
  );
}

FavoritesPage.getLayout = getGlobalExplorerLayout;
