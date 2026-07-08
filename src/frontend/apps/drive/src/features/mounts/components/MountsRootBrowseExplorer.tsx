import { MountDiscovery } from "@/features/drivers/types";
import { AppExplorerProps } from "@/features/explorer/components/app-view/AppExplorer";
import { BrowseExplorerTemplate } from "@/features/explorer/components/shared-browse/BrowseExplorerTemplate";
import { discoveryToMountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { DefaultRoute } from "@/utils/defaultRoutes";
import React from "react";
import { useTranslation } from "react-i18next";

type MountsRootBrowseExplorerProps = Pick<
  AppExplorerProps,
  "selectionBarActions" | "getContextMenuItems" | "gridHeader" | "onNavigate"
> & {
  mounts?: MountDiscovery[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

const mapMountDiscoveryPageItems = (page: MountDiscovery[]) => {
  return page.map(discoveryToMountExplorerItem);
};

export const MountsRootBrowseExplorer = ({
  mounts,
  isLoading,
  isError,
  onRetry,
  ...appExplorerProps
}: MountsRootBrowseExplorerProps) => {
  const { t } = useTranslation();

  return (
    <BrowseExplorerTemplate
      data={mounts ? { pages: [mounts] } : undefined}
      mapPageItems={mapMountDiscoveryPageItems}
      isLoading={isLoading}
      isError={isError || !mounts}
      loadingLabel={t("explorer.mounts.loading")}
      errorLabel={t("explorer.mounts.error")}
      onRetry={onRetry}
      showFilters={false}
      viewConfigKey={DefaultRoute.MOUNTS}
      preserveIdleTopBarSpace
      disableItemDragAndDrop
      disableDefaultContextMenu
      {...appExplorerProps}
    />
  );
};
