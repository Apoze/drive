import React from "react";
import { useRouter } from "next/router";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { MenuItem } from "@gouvfr-lasuite/ui-kit";
import {
  NavigationEventType,
  useGlobalExplorer,
} from "@/features/explorer/components/GlobalExplorerContext";
import { getDriver } from "@/features/config/Config";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { MountExplorerBreadcrumbs } from "@/features/mounts/components/MountExplorerBreadcrumbs";
import { MountsRootBrowseExplorer } from "@/features/mounts/components/MountsRootBrowseExplorer";
import { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { getMountActionIds } from "@/features/mounts/utils/mountActionConfig";

const MountsSelectionBarActions = ({
  onBrowse,
}: {
  onBrowse: (item: MountExplorerItem) => void;
}) => {
  const { t } = useTranslation();
  const { selectedItems } = useGlobalExplorer();

  if (selectedItems.length !== 1) {
    return null;
  }

  const item = selectedItems[0] as MountExplorerItem;
  if (!getMountActionIds(item).includes("browse")) {
    return null;
  }

  return (
    <Button variant="tertiary" size="small" onClick={() => onBrowse(item)}>
      {t("explorer.mounts.browse")}
    </Button>
  );
};

export default function MountsPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const { openRightPanelForItem } = useGlobalExplorer();

  useDefaultRoute(DefaultRoute.MOUNTS);

  const {
    data: mounts,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["mounts", "discovery"],
    refetchOnWindowFocus: false,
    queryFn: () => getDriver().getMountsDiscovery(),
  });

  const handleBrowseMount = (mountItem: MountExplorerItem) => {
    void router.push({
      pathname: "/explorer/mounts/[mount_id]",
      query: {
        mount_id: mountItem.mountMeta.mountId,
        path: mountItem.mountMeta.normalizedPath,
      },
    });
  };

  const handleShowInfo = (mountItem: MountExplorerItem) => {
    openRightPanelForItem(mountItem);
  };

  const getMenuItems = (mountItem: MountExplorerItem): MenuItem[] => {
    const actionIds = getMountActionIds(mountItem);

    return [
      {
        icon: <span className="material-icons">folder_open</span>,
        label: t("explorer.mounts.browse"),
        isHidden: !actionIds.includes("browse"),
        callback: () => handleBrowseMount(mountItem),
      },
      {
        icon: <span className="material-icons">info</span>,
        label: t("explorer.item.actions.view_info"),
        isHidden: !actionIds.includes("view_info"),
        callback: () => handleShowInfo(mountItem),
      },
    ];
  };

  return (
    <MountsRootBrowseExplorer
      mounts={mounts}
      isLoading={isLoading}
      isError={isError}
      onRetry={() => {
        void refetch();
      }}
      selectionBarActions={
        <MountsSelectionBarActions onBrowse={handleBrowseMount} />
      }
      getContextMenuItems={(item) => getMenuItems(item as MountExplorerItem)}
      gridHeader={<MountExplorerBreadcrumbs />}
      onNavigate={(event) => {
        if (event.type !== NavigationEventType.ITEM) {
          return;
        }
        handleBrowseMount(event.item as MountExplorerItem);
      }}
    />
  );
}

MountsPage.getLayout = getGlobalExplorerLayout;
