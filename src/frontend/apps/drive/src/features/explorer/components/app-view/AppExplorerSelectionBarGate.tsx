import React from "react";
import { HorizontalSeparator } from "@gouvfr-lasuite/ui-kit";
import { ExplorerFilters } from "@/features/explorer/components/app-view/ExplorerFilters";
import { ExplorerSelectionBar } from "@/features/explorer/components/app-view/ExplorerSelectionBar";
import { useHasSelection } from "@/features/explorer/stores/selectionStore";

export const AppExplorerSelectionBarGate = ({
  showFilters,
  preserveIdleTopBarSpace,
}: {
  showFilters: boolean;
  preserveIdleTopBarSpace: boolean;
}) => {
  const hasSelection = useHasSelection();

  if (hasSelection) {
    return <ExplorerSelectionBar />;
  }
  if (showFilters) {
    return <ExplorerFilters />;
  }
  if (preserveIdleTopBarSpace) {
    return <div className="explorer__filters explorer__filters--placeholder" />;
  }
  return <HorizontalSeparator withPadding={false} />;
};
