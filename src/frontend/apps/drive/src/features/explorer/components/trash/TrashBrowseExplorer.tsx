import { getDriver } from "@/features/config/Config";
import { ItemFilters } from "@/features/drivers/Driver";
import { Item } from "@/features/drivers/types";
import { AppExplorerProps } from "@/features/explorer/components/app-view/AppExplorer";
import { BrowseExplorerTemplate } from "@/features/explorer/components/shared-browse/BrowseExplorerTemplate";
import { useQuery } from "@tanstack/react-query";
import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { DefaultRoute } from "@/utils/defaultRoutes";

type TrashBrowseExplorerProps = Pick<
  AppExplorerProps,
  | "gridActionsCell"
  | "gridHeader"
  | "selectionBarActions"
  | "onNavigate"
  | "onFileClick"
> & {
  viewConfigKey?: DefaultRoute.TRASH;
};

const mapTrashPageItems = (page: Item[]) => page;

export const TrashBrowseExplorer = ({
  viewConfigKey = DefaultRoute.TRASH,
  ...appExplorerProps
}: TrashBrowseExplorerProps) => {
  const { t } = useTranslation();
  const [filters, setFilters] = useState<ItemFilters>({});
  const {
    data: trashItems,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: [
      "items",
      "trash",
      ...(Object.keys(filters).length ? [JSON.stringify(filters)] : []),
    ],
    queryFn: () => getDriver().getTrashItems(filters),
  });

  return (
    <BrowseExplorerTemplate
      data={trashItems ? { pages: [trashItems] } : undefined}
      mapPageItems={mapTrashPageItems}
      isLoading={isLoading}
      isError={isError || !trashItems}
      loadingLabel={t("explorer.trash.loading")}
      errorLabel={t("explorer.trash.error")}
      onRetry={() => {
        void refetch();
      }}
      disableItemDragAndDrop
      viewConfigKey={viewConfigKey}
      defaultBaseFilters={{}}
      onComputedFiltersChange={setFilters}
      {...appExplorerProps}
    />
  );
};
