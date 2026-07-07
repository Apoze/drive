import React from "react";
import { Item } from "@/features/drivers/types";
import { useTranslation } from "react-i18next";
import { useGlobalExplorer } from "../GlobalExplorerContext";
import clsx from "clsx";
import gridEmpty from "@/assets/grid_empty.png";
import starEmpty from "@/assets/star_tab_empty.svg";
import { useAppExplorer } from "@/features/explorer/components/app-view/AppExplorer";
import { EmbeddedExplorerGrid } from "../embedded-explorer/EmbeddedExplorerGrid";
import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";
import { InfiniteScroll } from "@/features/ui/components/infinite-scroll/InfiniteScroll";
import { useRouter } from "next/router";
import { DefaultRoute, getDefaultRouteId } from "@/utils/defaultRoutes";
import { useMemo, useState } from "react";
import { canCreateChildren } from "@/features/items/utils";
import { Spinner } from "@gouvfr-lasuite/ui-kit";
import { openWopiInNewTab } from "@/features/ui/preview/wopi/openWopi";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { ConvertLegacyFileModal } from "@/features/explorer/components/modals/ConvertLegacyFileModal";

/**
 * Wrapper around EmbeddedExplorerGrid to display a list of items in a table.
 *
 * It provides:
 * - Runtime tree lazy loading support
 *
 * TODO: Refactor using EmbeddedExplorer
 *
 */
export const AppExplorerGrid = () => {
  const { t } = useTranslation();
  const appExplorer = useAppExplorer();

  const router = useRouter();

  const {
    onNavigate,
    clearRightPanelItem,
    item,
    displayMode,
    openPreview,
  } = useGlobalExplorer();

  const effectiveOnNavigate = appExplorer.onNavigate ?? onNavigate;
  const convertModal = useModal();
  const [itemToConvert, setItemToConvert] = useState<Item | null>(null);

  const handleFileClick = (item: Item) => {
    if (appExplorer.onFileClick) {
      appExplorer.onFileClick(item);
      return;
    }
    if (item.abilities?.convert) {
      setItemToConvert(item);
      convertModal.open();
      return;
    }
    if (item.is_wopi_supported) {
      openWopiInNewTab(item.id);
      return;
    }
    if (item.url) {
      openPreview(item, appExplorer.childrenItems ?? []);
    } else {
      addToast(<ToasterItem>{t("explorer.grid.no_url")}</ToasterItem>);
    }
  };

  const isLoading =
    appExplorer.isLoading || appExplorer.childrenItems === undefined;
  const isEmpty = appExplorer.childrenItems?.length === 0;

  const canAddChildren = item
    ? canCreateChildren(item, router.pathname)
    : false;

  const defaultRouteId = getDefaultRouteId(router.pathname);
  const emptyCTATranslationSuffix = useMemo(() => {
    if (defaultRouteId === DefaultRoute.MY_FILES) {
      return ".default";
    }
    if (defaultRouteId) {
      return `.${defaultRouteId}`.replaceAll("-", "_");
    }
    if (!canAddChildren) {
      return ".no_create";
    }
    return ".default";
  }, [defaultRouteId, canAddChildren]);

  const emptyCaptionTranslationSuffix = useMemo(() => {
    if (defaultRouteId) {
      return `.default`;
    }
    return ".folder";
  }, [defaultRouteId]);

  const getContent = () => {
    if (isEmpty) {
      return (
        <div className="c__datagrid__empty-placeholder fs-h3 clr-greyscale-900 fw-bold">
          <img
            src={
              defaultRouteId === DefaultRoute.FAVORITES
                ? starEmpty.src
                : gridEmpty.src
            }
            alt={t("components.datagrid.empty_alt")}
            className="explorer__grid__empty__image"
          />
          <div className="explorer__grid__empty">
            <div className="explorer__grid__empty__caption">
              {t(
                `explorer.grid.empty.caption${emptyCaptionTranslationSuffix}`,
              )}
            </div>
            <div className="explorer__grid__empty__cta">
              {t(`explorer.grid.empty.cta${emptyCTATranslationSuffix}`)}
            </div>
          </div>
        </div>
      );
    }

    if (!appExplorer.childrenItems) {
      return null;
    }

    const gridContent = (
      <EmbeddedExplorerGrid
        items={appExplorer.childrenItems}
        parentItem={item}
        gridActionsCell={appExplorer.gridActionsCell}
        onNavigate={effectiveOnNavigate}
        clearRightPanelItem={clearRightPanelItem}
        disableItemDragAndDrop={appExplorer.disableItemDragAndDrop}
        enableMetaKeySelection={true}
        displayMode={displayMode}
        canSelect={appExplorer.canSelect}
        getContextMenuItems={appExplorer.getContextMenuItems}
        onFileClick={handleFileClick}
        sortState={appExplorer.sortState}
        onSort={appExplorer.onSort}
        prefs={appExplorer.prefs}
        onChangeColumn={appExplorer.onChangeColumn}
        column1Config={appExplorer.column1Config}
        column2Config={appExplorer.column2Config}
      />
    );

    // If infinite scroll props are provided, wrap with InfiniteScroll
    if (appExplorer.hasNextPage !== undefined && appExplorer.fetchNextPage) {
      return (
        <InfiniteScroll
          hasNextPage={appExplorer.hasNextPage}
          isFetchingNextPage={appExplorer.isFetchingNextPage || false}
          fetchNextPage={appExplorer.fetchNextPage}
        >
          {gridContent}
        </InfiniteScroll>
      );
    }

    return gridContent;
  };

  return (
    <div
      className={clsx("c__datagrid explorer__grid", {
        "c__datagrid--empty": isEmpty,
        "c__datagrid--loading": isLoading,
      })}
    >
      {getContent()}
      {isLoading && (
        <div className="explorer__grid__loading-overlay">
          <Spinner size="xl" />
        </div>
      )}
      {convertModal.isOpen && itemToConvert && (
        <ConvertLegacyFileModal
          item={itemToConvert}
          isOpen={convertModal.isOpen}
          onClose={convertModal.onClose}
        />
      )}
    </div>
  );
};
