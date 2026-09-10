import React from "react";
import type { ReactNode } from "react";
import { useState } from "react";

import { IconSize, type MenuItem } from "@gouvfr-lasuite/ui-kit";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { useRouter } from "next/router";
import { useConfig } from "@/features/config/ConfigProvider";

import createFolderSvg from "@/assets/icons/create_folder.svg";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import { Item, ItemType } from "@/features/drivers/types";

import { docsCreationUrl } from "../utils/docsNavigation";

import { ItemIcon } from "../components/icons/ItemIcon";
import {
  ExplorerCreateFileModal,
  ExplorerCreateFileType,
} from "../components/modals/ExplorerCreateFileModal";
import { ExplorerCreateFolderModal } from "../components/modals/ExplorerCreateFolderModal";
import { buildItemImportMenuItems } from "../components/item-actions/itemImportMenuItems";
import {
  DefaultRoute,
  getDefaultRouteId,
  isMyFilesRoute,
} from "@/utils/defaultRoutes";

type UseCreateMenuItemsProps = {
  includeImport?: boolean;
};

type UseCreateMenuItemsReturn = {
  menuItems: MenuItem[];
  modals: ReactNode;
};

const renderFileIcon = (item: Partial<Item>) => {
  return (
    <div>
      <ItemIcon item={item as Item} size={IconSize.MEDIUM} type="mini" />
    </div>
  );
};

/**
 * Hybrid hook (upstream structure + fork UX):
 * - Provides menu items + renders modals from a single place.
 * - Preserves fork "Plus de formats…" entry by opening the advanced create modal
 *   (ExplorerCreateFileModal with type unset).
 */
export const useCreateMenuItems = ({
  includeImport = false,
}: UseCreateMenuItemsProps = {}): UseCreateMenuItemsReturn => {
  const { t } = useTranslation();
  const router = useRouter();
  const { config } = useConfig();
  const { displayMode, item, itemId } = useGlobalExplorer();

  const defaultRouteId = getDefaultRouteId(router.pathname);
  const isRegularCreateSurface =
    displayMode === "app" &&
    defaultRouteId !== DefaultRoute.MOUNTS &&
    defaultRouteId !== DefaultRoute.TRASH;
  const isVirtualCreateFallbackRoute =
    defaultRouteId === DefaultRoute.RECENT ||
    defaultRouteId === DefaultRoute.SHARED_WITH_ME ||
    defaultRouteId === DefaultRoute.FAVORITES;
  const canCreateHere = isVirtualCreateFallbackRoute
    ? false
    : (item?.abilities?.children_create ?? true);
  const effectiveParentId = canCreateHere ? itemId : undefined;
  const shouldRedirectAfterFallback =
    !canCreateHere && !isMyFilesRoute(router.pathname);
  const requiresSpace =
    config.STORAGE_UNIFIED_ENABLED && !item?.abilities.children_create;
  const isCreateHidden = !isRegularCreateSurface || requiresSpace;
  const isFileCreateHidden = isCreateHidden || item?.type === ItemType.DOCS;
  const isImportHidden =
    !isRegularCreateSurface ||
    !canCreateHere ||
    requiresSpace ||
    item?.type === ItemType.DOCS;

  const createFolderModal = useModal();
  const createFileModal = useModal();
  const [createFileModalType, setCreateFileModalType] = useState<
    ExplorerCreateFileType | undefined
  >(undefined);

  const openCreateFileModal = (type?: ExplorerCreateFileType) => {
    setCreateFileModalType(type);
    createFileModal.open();
  };

  const docsUrl =
    config.DOCS_DRIVE_ENABLED &&
    docsCreationUrl(
      config.DOCS_PUBLIC_URL,
      effectiveParentId,
      typeof router.query?.space === "string" ? router.query.space : undefined,
    );
  const items: MenuItem[] = [
    {
      icon: renderFileIcon({ type: ItemType.DOCS }),
      label: t("explorer.actions.createDocs"),
      isHidden: isCreateHidden || !docsUrl,
      callback: () => {
        if (docsUrl) window.open(docsUrl, "_blank", "noopener,noreferrer");
      },
    },
    {
      icon: <img src={createFolderSvg.src} alt="" />,
      label: t("explorer.actions.createFolder.modal.title"),
      isHidden: isFileCreateHidden,
      callback: createFolderModal.open,
    },
    { type: "separator" },
  ];

  if (includeImport) {
    items.push(
      ...buildItemImportMenuItems({
        t,
        isHidden: isImportHidden,
      }),
      { type: "separator" },
    );
  }

  items.push(
    {
      icon: renderFileIcon({
        type: ItemType.FILE,
        filename: "document.odt",
        mimetype: "application/vnd.oasis.opendocument.text",
      }),
      label: t("explorer.tree.create.file.doc"),
      isHidden: isFileCreateHidden,
      callback: () => openCreateFileModal(ExplorerCreateFileType.DOC),
    },
    {
      icon: renderFileIcon({
        type: ItemType.FILE,
        filename: "spreadsheet.ods",
        mimetype: "application/vnd.oasis.opendocument.spreadsheet",
      }),
      label: t("explorer.tree.create.file.calc"),
      isHidden: isFileCreateHidden,
      callback: () => openCreateFileModal(ExplorerCreateFileType.CALC),
    },
    {
      icon: renderFileIcon({
        type: ItemType.FILE,
        filename: "presentation.odp",
        mimetype: "application/vnd.oasis.opendocument.presentation",
      }),
      label: t("explorer.tree.create.file.powerpoint"),
      isHidden: isFileCreateHidden,
      callback: () => openCreateFileModal(ExplorerCreateFileType.POWERPOINT),
    },
    {
      icon: <span className="material-icons">more_horiz</span>,
      label: t("explorer.tree.create.file.more_formats"),
      isHidden: isFileCreateHidden,
      callback: () => openCreateFileModal(undefined),
    },
  );

  const modals = (
    <>
      <ExplorerCreateFolderModal
        {...createFolderModal}
        parentId={effectiveParentId}
        redirectAfterCreate={shouldRedirectAfterFallback}
      />
      <ExplorerCreateFileModal
        {...createFileModal}
        parentId={effectiveParentId}
        canCreateChildren={canCreateHere}
        redirectAfterCreate={shouldRedirectAfterFallback}
        type={createFileModalType}
      />
    </>
  );

  return { menuItems: items, modals };
};
