import { useMemo } from "react";
import { useRouter } from "next/router";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { AppExplorer } from "@/features/explorer/components/app-view/AppExplorer";
import { NavigationEventType } from "@/features/explorer/components/GlobalExplorerContext";
import { getDriver } from "@/features/config/Config";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { MountExplorerBreadcrumbs } from "@/features/mounts/components/MountExplorerBreadcrumbs";
import { discoveryToMountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";
import { DefaultRoute } from "@/utils/defaultRoutes";

export default function MountsPage() {
  const { t } = useTranslation();
  const router = useRouter();

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

  const mountItems = useMemo(
    () => mounts?.map(discoveryToMountExplorerItem) ?? [],
    [mounts],
  );

  if (isLoading) {
    return <div>{t("explorer.mounts.loading")}</div>;
  }

  if (isError || !mounts) {
    return (
      <div>
        <div>{t("explorer.mounts.error")}</div>
        <Button variant="tertiary" onClick={() => refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    );
  }

  return (
    <AppExplorer
      childrenItems={mountItems}
      showFilters={false}
      preserveIdleTopBarSpace
      disableItemDragAndDrop
      disableDefaultContextMenu
      selectionBarActions={<></>}
      gridActionsCell={() => null}
      getContextMenuItems={() => []}
      gridHeader={<MountExplorerBreadcrumbs />}
      onNavigate={(event) => {
        if (event.type !== NavigationEventType.ITEM) {
          return;
        }
        const mountItem = event.item as (typeof mountItems)[number];
        void router.push({
          pathname: "/explorer/mounts/[mount_id]",
          query: {
            mount_id: mountItem.mountMeta.mountId,
            path: mountItem.mountMeta.normalizedPath,
          },
        });
      }}
    />
  );
}

MountsPage.getLayout = getGlobalExplorerLayout;
