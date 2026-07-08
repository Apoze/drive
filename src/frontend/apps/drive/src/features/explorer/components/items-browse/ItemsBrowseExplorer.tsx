import { ItemFilters } from "@/features/drivers/Driver";
import { BrowseExplorerTemplate } from "@/features/explorer/components/shared-browse/BrowseExplorerTemplate";
import { useInfiniteChildren } from "@/features/explorer/hooks/useInfiniteChildren";
import {
  useInfiniteItems,
  useInfiniteRecentItems,
} from "@/features/explorer/hooks/useInfiniteItems";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import { CustomFilesPreview } from "@/features/ui/preview/custom-files-preview/CustomFilesPreview";
import React, { useState } from "react";
import { mapItemsBrowsePageItems } from "./itemsBrowseUtils";
import { DefaultRoute } from "@/utils/defaultRoutes";

type ItemsRootBrowseProps = {
  kind: "items";
  defaultFilters: ItemFilters;
  showFilters?: boolean;
  viewConfigKey?: DefaultRoute;
};

type ItemChildrenBrowseProps = {
  kind: "children";
  itemId: string | null;
  defaultFilters?: ItemFilters;
  showFilters?: boolean;
  viewConfigKey?: "folder";
  navigationId?: string;
};

type RecentItemsBrowseProps = {
  kind: "recent";
  defaultFilters: ItemFilters;
  showFilters?: boolean;
  viewConfigKey?: DefaultRoute.RECENT;
};

export type ItemsBrowseExplorerProps =
  | ItemsRootBrowseProps
  | ItemChildrenBrowseProps
  | RecentItemsBrowseProps;

const ItemsBrowsePreviewHost = () => {
  const {
    previewItem,
    previewItems,
    setPreviewCurrentItem,
    replacePreviewItems,
  } = useGlobalExplorer();

  return (
    <CustomFilesPreview
      currentItem={previewItem}
      items={previewItems}
      setPreviewCurrentItem={setPreviewCurrentItem}
      onItemsChange={replacePreviewItems}
    />
  );
};

const ItemsRootBrowseExplorer = ({
  defaultFilters,
  showFilters = true,
  viewConfigKey = DefaultRoute.MY_FILES,
}: ItemsRootBrowseProps) => {
  const [filters, setFilters] = useState<ItemFilters>(defaultFilters);
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteItems(filters);

  return (
    <BrowseExplorerTemplate
      data={data}
      mapPageItems={mapItemsBrowsePageItems}
      viewConfigKey={viewConfigKey}
      defaultBaseFilters={defaultFilters}
      onComputedFiltersChange={setFilters}
      hasNextPage={hasNextPage}
      showFilters={showFilters}
      isFetchingNextPage={isFetchingNextPage}
      fetchNextPage={fetchNextPage}
      isLoading={isLoading}
      renderAfterExplorer={() => <ItemsBrowsePreviewHost />}
    />
  );
};

const ItemChildrenBrowseExplorer = ({
  itemId,
  defaultFilters = {},
  showFilters = true,
  viewConfigKey = "folder",
  navigationId,
}: ItemChildrenBrowseProps) => {
  const [filters, setFilters] = useState<ItemFilters>(defaultFilters);
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteChildren(itemId, filters);

  return (
    <BrowseExplorerTemplate
      data={data}
      mapPageItems={mapItemsBrowsePageItems}
      viewConfigKey={viewConfigKey}
      navigationId={navigationId}
      defaultBaseFilters={defaultFilters}
      onComputedFiltersChange={setFilters}
      hasNextPage={hasNextPage}
      showFilters={showFilters}
      isFetchingNextPage={isFetchingNextPage}
      fetchNextPage={fetchNextPage}
      isLoading={isLoading}
      renderAfterExplorer={() => <ItemsBrowsePreviewHost />}
    />
  );
};

const RecentItemsBrowseExplorer = ({
  defaultFilters,
  showFilters = true,
  viewConfigKey = DefaultRoute.RECENT,
}: RecentItemsBrowseProps) => {
  const [filters, setFilters] = useState<ItemFilters>(defaultFilters);
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteRecentItems(filters);

  return (
    <BrowseExplorerTemplate
      data={data}
      mapPageItems={mapItemsBrowsePageItems}
      viewConfigKey={viewConfigKey}
      defaultBaseFilters={defaultFilters}
      onComputedFiltersChange={setFilters}
      hasNextPage={hasNextPage}
      showFilters={showFilters}
      isFetchingNextPage={isFetchingNextPage}
      fetchNextPage={fetchNextPage}
      isLoading={isLoading}
      renderAfterExplorer={() => <ItemsBrowsePreviewHost />}
    />
  );
};

export const ItemsBrowseExplorer = (props: ItemsBrowseExplorerProps) => {
  if (props.kind === "items") {
    return <ItemsRootBrowseExplorer {...props} />;
  }

  if (props.kind === "recent") {
    return <RecentItemsBrowseExplorer {...props} />;
  }

  return <ItemChildrenBrowseExplorer {...props} />;
};
