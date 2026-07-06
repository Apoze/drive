import React from "react";
import { ItemFilters } from "@/features/drivers/Driver";
import { ItemsBrowseExplorer } from "@/features/explorer/components/items-browse/ItemsBrowseExplorer";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { getFromRoute } from "@/features/explorer/utils/utils";

export type WorkspacesExplorerProps = {
  readonly defaultFilters: ItemFilters;
  readonly showFilters?: boolean;
  readonly viewConfigKey?: DefaultRoute;
};

export default function WorkspacesExplorer({
  defaultFilters,
  showFilters = true,
  viewConfigKey,
}: WorkspacesExplorerProps) {
  const browserRoute =
    typeof window === "undefined"
      ? null
      : (getFromRoute() as DefaultRoute | null);
  const resolvedViewConfigKey =
    viewConfigKey ?? browserRoute ?? DefaultRoute.MY_FILES;

  return (
    <ItemsBrowseExplorer
      kind="items"
      defaultFilters={defaultFilters}
      showFilters={showFilters}
      viewConfigKey={resolvedViewConfigKey}
    />
  );
}
