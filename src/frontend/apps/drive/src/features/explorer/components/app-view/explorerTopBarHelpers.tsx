import React, { type ReactNode } from "react";
import { TFunction } from "i18next";
import { FilterOption, IconSize } from "@gouvfr-lasuite/ui-kit";
import folderIcon from "@/assets/folder/folder.svg";
import mimeOther from "@/assets/files/icons/mime-other.svg";
import { Item, ItemBreadcrumb, ItemType } from "@/features/drivers/types";
import { ItemFilters, ItemFiltersScope } from "@/features/drivers/Driver";
import {
  DefaultRoute,
  getDefaultRouteId,
  isDefaultRoute,
  ORDERED_DEFAULT_ROUTES,
} from "@/utils/defaultRoutes";
import { getItemTitle } from "../../utils/utils";

export const ALL_FILTER_VALUE = "all";

export const shouldShowAppBreadcrumbActions = ({
  pathname,
  item,
}: {
  pathname: string;
  item?: Pick<Item, "abilities">;
}) => {
  const onDefaultRoute = isDefaultRoute(pathname);
  const defaultRouteId = getDefaultRouteId(pathname);

  return (
    (onDefaultRoute && defaultRouteId === DefaultRoute.MY_FILES) ||
    (!onDefaultRoute && item?.abilities?.children_create)
  );
};

export const getMobileBreadcrumbState = (
  breadcrumb?: ItemBreadcrumb[] | null,
) => {
  if (!breadcrumb || breadcrumb.length === 0) {
    return null;
  }

  const workspace = breadcrumb[0];
  const current = breadcrumb[breadcrumb.length - 1];
  const parent = breadcrumb[breadcrumb.length - 2] ?? workspace;

  return {
    workspace,
    current,
    parent,
    isRoot: current.id === workspace.id,
  };
};

export const resolveMobileBreadcrumbBackTarget = (parentId?: string) => {
  if (parentId === DefaultRoute.SHARED_WITH_ME) {
    return "/explorer/items/shared-with-me";
  }
  if (parentId === DefaultRoute.MY_FILES) {
    return "/explorer/items/my-files";
  }
  if (parentId === DefaultRoute.FAVORITES) {
    return "/explorer/items/favorites";
  }
  if (parentId === DefaultRoute.RECENT) {
    return "/explorer/items/recent";
  }

  return undefined;
};

export const getDefaultRouteDataByPath = (pathname: string) => {
  const defaultRouteId = getDefaultRouteId(pathname);
  return ORDERED_DEFAULT_ROUTES.find((route) => route.id === defaultRouteId);
};

export const handleFilterChange = (
  filters: ItemFilters = {},
  name: string,
  value: string | null,
) => {
  if (value === ALL_FILTER_VALUE) {
    const newFilters = { ...filters };
    delete newFilters[name as keyof ItemFilters];
    return newFilters;
  }

  return { ...filters, [name]: value };
};

export const buildFilterResetOption = (t: TFunction): FilterOption => ({
  label: t("explorer.filters.type.options.reset"),
  render: () => (
    <div className="explorer__filters__item">
      <span className="material-icons">undo</span>
      {t("explorer.filters.type.options.reset")}
    </div>
  ),
  value: ALL_FILTER_VALUE,
});

export const buildExplorerTypeFilterOptions = (
  t: TFunction,
): FilterOption[] => [
  {
    label: t("explorer.filters.type.options.folder"),
    value: ItemType.FOLDER,
    render: () => (
      <div className="explorer__filters__item">
        <img src={folderIcon.src} alt="" width="24" height="24" />
        {t("explorer.filters.type.options.folder")}
      </div>
    ),
  },
  {
    label: t("explorer.filters.type.options.file"),
    render: () => (
      <div className="explorer__filters__item">
        <img src={mimeOther.src} alt="" width="24" height="24" />
        {t("explorer.filters.type.options.file")}
      </div>
    ),
    value: ItemType.FILE,
    showSeparator: true,
  },
  buildFilterResetOption(t),
];

export const buildExplorerWorkspaceFilterOptions = ({
  items,
  t,
  renderIcon,
}: {
  items?: Item[];
  t: TFunction;
  renderIcon: (item: Item) => ReactNode;
}): FilterOption[] => [
  ...(items?.map((item) => ({
    label: item.title,
    value: item.id,
    render: () => (
      <div className="explorer__filters__item">
        {renderIcon(item)}
        {getItemTitle(item)}
      </div>
    ),
  })) ?? []),
  buildFilterResetOption(t),
];

export const buildExplorerScopeFilterOptions = (
  t: TFunction,
): FilterOption[] => [
  {
    label: t("explorer.filters.scopes.options.trash"),
    value: ItemFiltersScope.DELETED,
    render: () => (
      <div className="explorer__filters__item">
        {t("explorer.filters.scopes.options.trash")}
      </div>
    ),
    showSeparator: true,
  },
  buildFilterResetOption(t),
];

export const getWorkspaceIconSize = () => IconSize.SMALL;
