import React from "react";
import { ItemFilters } from "@/features/drivers/Driver";
import { ItemsBrowseExplorer } from "@/features/explorer/components/items-browse/ItemsBrowseExplorer";

export type WorkspacesExplorerProps = {
  readonly defaultFilters: ItemFilters;
  readonly showFilters?: boolean;
};
export default function WorkspacesExplorer({
  defaultFilters,
  showFilters = true,
}: WorkspacesExplorerProps) {
  return (
    <ItemsBrowseExplorer
      kind="items"
      defaultFilters={defaultFilters}
      showFilters={showFilters}
    />
  );
}
