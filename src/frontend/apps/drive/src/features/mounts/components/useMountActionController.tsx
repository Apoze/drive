import { errorToString } from "@/features/api/APIError";
import { getDriver } from "@/features/config/Config";
import {
  NavigationEvent,
  NavigationEventType,
  useGlobalExplorer,
} from "@/features/explorer/components/GlobalExplorerContext";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { MenuItem } from "@gouvfr-lasuite/ui-kit";
import { useRouter } from "next/router";
import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";
import {
  getMountBulkSelectionState,
  getParentMountPath,
} from "@/features/mounts/utils/mountBulkActions";
import {
  entryToMountExplorerItem,
  getMountExplorerMeta,
  type MountExplorerItem,
} from "@/features/mounts/utils/mountExplorerItems";
import {
  getMountContextMenuActionIds,
  getMountSelectionBarActionIds,
} from "@/features/mounts/components/mountActionControllerView";
import { createAndCopyMountShareLink } from "@/features/mounts/utils/mountShareLink";
import { createMountPreviewController } from "@/features/mounts/components/mountPreviewController";

const buildBrowseRoute = (mountId: string, path: string) => ({
  pathname: "/explorer/mounts/[mount_id]",
  query: { mount_id: mountId, path },
});

const buildWopiRoute = (mountId: string, path: string) => ({
  pathname: "/explorer/mounts/[mount_id]/wopi",
  query: { mount_id: mountId, path },
});

const MountSelectionBarActions = ({
  onBrowse,
  onPreview,
  onDownload,
  onDuplicate,
  onWopi,
  onShare,
  onMove,
  onRename,
  onDelete,
}: {
  onBrowse: (items: MountExplorerItem[]) => void;
  onPreview: (items: MountExplorerItem[]) => void;
  onDownload: (items: MountExplorerItem[]) => void;
  onDuplicate: (items: MountExplorerItem[]) => void;
  onWopi: (items: MountExplorerItem[]) => void;
  onShare: (items: MountExplorerItem[]) => void;
  onMove: (items: MountExplorerItem[]) => void;
  onRename: (items: MountExplorerItem[]) => void;
  onDelete: (items: MountExplorerItem[]) => void;
}) => {
  const { t } = useTranslation();
  const { selectedItems } = useGlobalExplorer();

  if (selectedItems.length === 0) {
    return null;
  }

  const mountItems = selectedItems as MountExplorerItem[];
  const selectionActionIds = getMountSelectionBarActionIds(mountItems);
  const actionButtons = {
    browse: (
      <Button
        key="browse"
        variant="tertiary"
        size="small"
        onClick={() => onBrowse(mountItems)}
      >
        {t("explorer.mounts.browse")}
      </Button>
    ),
    preview: (
      <Button
        key="preview"
        variant="tertiary"
        size="small"
        onClick={() => onPreview(mountItems)}
      >
        {t("explorer.mounts.actions.preview")}
      </Button>
    ),
    share: (
      <Button
        key="share"
        variant="tertiary"
        size="small"
        onClick={() => onShare(mountItems)}
      >
        {t("explorer.mounts.actions.share")}
      </Button>
    ),
    download: (
      <Button
        key="download"
        variant="tertiary"
        size="small"
        onClick={() => onDownload(mountItems)}
      >
        {t("explorer.mounts.actions.download")}
      </Button>
    ),
    duplicate: (
      <Button
        key="duplicate"
        variant="tertiary"
        size="small"
        onClick={() => onDuplicate(mountItems)}
      >
        {t("explorer.mounts.actions.duplicate")}
      </Button>
    ),
    wopi: (
      <Button
        key="wopi"
        variant="tertiary"
        size="small"
        onClick={() => onWopi(mountItems)}
      >
        {t("explorer.mounts.actions.wopi")}
      </Button>
    ),
    rename: (
      <Button
        key="rename"
        variant="tertiary"
        size="small"
        onClick={() => onRename(mountItems)}
      >
        {t("explorer.item.actions.rename")}
      </Button>
    ),
    move: (
      <Button
        key="move"
        variant="tertiary"
        size="small"
        onClick={() => onMove(mountItems)}
      >
        {t("explorer.item.actions.move")}
      </Button>
    ),
    delete: (
      <Button
        key="delete"
        variant="tertiary"
        size="small"
        onClick={() => onDelete(mountItems)}
      >
        {t("explorer.item.actions.delete")}
      </Button>
    ),
  } as const;

  return (
    <>
      {selectionActionIds.map((actionId) =>
        actionId === "separator" || actionId === "view_info"
          ? null
          : (actionButtons[actionId] ?? null),
      )}
    </>
  );
};

export const useMountActionController = ({
  mountId,
  mountTitle,
  provider,
  normalizedPath,
  onBrowseRefetch,
}: {
  mountId: string;
  mountTitle: string;
  provider?: string;
  normalizedPath: string;
  onBrowseRefetch: () => Promise<unknown> | void;
}) => {
  const { t } = useTranslation();
  const router = useRouter();
  const {
    openRightPanelForItem,
    replaceRightPanelItemIfCurrent,
    closeRightPanelIfCurrent,
    closeRightPanelIfIncluded,
    clearSelection,
    selectSingleItem,
  } = useGlobalExplorer();
  const [previewItem, setPreviewCurrentItem] = useState<MountExplorerItem>();
  const [actionItems, setActionItems] = useState<MountExplorerItem[]>([]);
  const activeActionItem = actionItems[0];
  const mountPreviewController = createMountPreviewController({
    previewItem,
    setPreviewCurrentItem,
  });

  const navigateToPath = (path: string) => {
    void router.push(buildBrowseRoute(mountId, path));
  };

  const handleBrowseItem = (item: MountExplorerItem) => {
    const meta = getMountExplorerMeta(item);
    navigateToPath(meta.normalizedPath);
  };

  const handlePreviewItem = (item: MountExplorerItem) => {
    mountPreviewController.openPreview(item);
  };

  const handleDownloadItem = (item: MountExplorerItem) => {
    if (!item.url) {
      return;
    }
    window.open(item.url, "_blank", "noreferrer");
  };

  const handleDuplicateItem = async (item: MountExplorerItem) => {
    const meta = getMountExplorerMeta(item);
    if (!meta.abilities?.duplicate) {
      return;
    }

    try {
      await getDriver().duplicateMountEntry({
        mountId: meta.mountId,
        path: meta.normalizedPath,
      });
      addToast(
        <ToasterItem>{t("explorer.mounts.duplicate.success")}</ToasterItem>,
      );
      await onBrowseRefetch();
    } catch (error) {
      addToast(
        <ToasterItem type="error">{errorToString(error)}</ToasterItem>,
      );
    }
  };

  const handleWopiItem = (item: MountExplorerItem) => {
    const meta = getMountExplorerMeta(item);
    void router.push(buildWopiRoute(meta.mountId, meta.normalizedPath));
  };

  const handleShareItem = async (item: MountExplorerItem) => {
    await createAndCopyMountShareLink(item);
  };

  const handleShowInfo = (item: MountExplorerItem) => {
    openRightPanelForItem(item);
  };

  const handleRenameRequest = (items: MountExplorerItem[]) => {
    if (items.length !== 1) {
      return;
    }
    setActionItems(items);
  };

  const handleMoveRequest = (items: MountExplorerItem[]) => {
    const selection = getMountBulkSelectionState(items);
    if (!selection.sameMount) {
      addToast(
        <ToasterItem type="error">{t("explorer.mounts.bulk.move.mixed_mount")}</ToasterItem>,
      );
      return;
    }
    if (!selection.canMove) {
      addToast(
        <ToasterItem type="error">
          {t("explorer.mounts.bulk.move.unsupported_selection")}
        </ToasterItem>,
      );
      return;
    }
    setActionItems(items);
  };

  const handleDeleteRequest = (items: MountExplorerItem[]) => {
    const selection = getMountBulkSelectionState(items);
    if (!selection.sameMount) {
      addToast(
        <ToasterItem type="error">
          {t("explorer.mounts.bulk.delete.mixed_mount")}
        </ToasterItem>,
      );
      return;
    }
    if (!selection.canDelete) {
      addToast(
        <ToasterItem type="error">
          {t("explorer.mounts.bulk.delete.unsupported_selection")}
        </ToasterItem>,
      );
      return;
    }
    setActionItems(items);
  };

  const handleRenameSuccess = (entry: Parameters<typeof entryToMountExplorerItem>[1]) => {
    if (!activeActionItem) {
      return;
    }
    const updatedItem = entryToMountExplorerItem(
      mountId,
      entry,
      mountTitle,
      provider,
    );
    selectSingleItem(updatedItem);
    replaceRightPanelItemIfCurrent(activeActionItem.id, updatedItem);
    mountPreviewController.closePreviewIfCurrent(activeActionItem.id);
    void onBrowseRefetch();
  };

  const handleMoveSuccess = (payload: {
    sourceItems: MountExplorerItem[];
    movedEntries: Parameters<typeof entryToMountExplorerItem>[1][];
    partialFailure?: {
      item: MountExplorerItem;
      completedCount: number;
      error: unknown;
    };
  }) => {
    if (payload.sourceItems.length === 0) {
      return;
    }

    if (!payload.partialFailure && payload.sourceItems.length === 1 && payload.movedEntries[0]) {
      const movedItem = entryToMountExplorerItem(
        mountId,
        payload.movedEntries[0],
        mountTitle,
        provider,
      );
      const remainsVisible =
        getParentMountPath(payload.movedEntries[0].normalized_path) === normalizedPath;

      if (remainsVisible) {
        selectSingleItem(movedItem);
        replaceRightPanelItemIfCurrent(payload.sourceItems[0].id, movedItem);
      } else {
        clearSelection();
        closeRightPanelIfCurrent(payload.sourceItems[0].id);
        mountPreviewController.closePreviewIfCurrent(payload.sourceItems[0].id);
      }
      void onBrowseRefetch();
      return;
    }

    const movedIds = new Set(payload.sourceItems.map((item) => item.id));
    clearSelection();
    closeRightPanelIfIncluded([...movedIds]);
    mountPreviewController.closePreviewIfIncluded(payload.sourceItems);
    void onBrowseRefetch();
  };

  const handleDeleteSuccess = (payload: {
    deletedItems: MountExplorerItem[];
    partialFailure?: {
      item: MountExplorerItem;
      completedCount: number;
      error: unknown;
    };
  }) => {
    if (payload.deletedItems.length === 0) {
      return;
    }
    clearSelection();
    closeRightPanelIfIncluded(payload.deletedItems);
    mountPreviewController.closePreviewIfIncluded(payload.deletedItems);
    void onBrowseRefetch();
  };

  const getContextMenuItems = (item: MountExplorerItem): MenuItem[] => {
    const contextActionIds = getMountContextMenuActionIds(item);
    const actionItems: Record<string, MenuItem> = {
      browse: {
        icon: <span className="material-icons">folder_open</span>,
        label: t("explorer.mounts.browse"),
        callback: () => handleBrowseItem(item),
      },
      preview: {
        icon: <span className="material-icons">visibility</span>,
        label: t("explorer.mounts.actions.preview"),
        callback: () => handlePreviewItem(item),
      },
      share: {
        icon: <span className="material-icons">share</span>,
        label: t("explorer.mounts.actions.share"),
        callback: () => void handleShareItem(item),
      },
      download: {
        icon: <span className="material-icons">download</span>,
        label: t("explorer.mounts.actions.download"),
        callback: () => handleDownloadItem(item),
      },
      duplicate: {
        icon: <span className="material-icons">content_copy</span>,
        label: t("explorer.mounts.actions.duplicate"),
        callback: () => void handleDuplicateItem(item),
      },
      wopi: {
        icon: <span className="material-icons">edit</span>,
        label: t("explorer.mounts.actions.wopi"),
        callback: () => handleWopiItem(item),
      },
      rename: {
        icon: <span className="material-icons">edit</span>,
        label: t("explorer.item.actions.rename"),
        callback: () => handleRenameRequest([item]),
      },
      move: {
        icon: <span className="material-icons">drive_file_move</span>,
        label: t("explorer.item.actions.move"),
        callback: () => handleMoveRequest([item]),
      },
      view_info: {
        icon: <span className="material-icons">info</span>,
        label: t("explorer.item.actions.view_info"),
        callback: () => handleShowInfo(item),
      },
      delete: {
        icon: <span className="material-icons">delete</span>,
        label: t("explorer.item.actions.delete"),
        variant: "danger" as const,
        callback: () => handleDeleteRequest([item]),
      },
      separator: { type: "separator" as const },
    };

    return contextActionIds.map((actionId) => actionItems[actionId]);
  };

  const selectionBarActions = (
    <MountSelectionBarActions
      onBrowse={(items) => handleBrowseItem(items[0])}
      onPreview={(items) => handlePreviewItem(items[0])}
      onDownload={(items) => handleDownloadItem(items[0])}
      onDuplicate={(items) => {
        void handleDuplicateItem(items[0]);
      }}
      onWopi={(items) => handleWopiItem(items[0])}
      onShare={(items) => {
        void handleShareItem(items[0]);
      }}
      onMove={handleMoveRequest}
      onRename={handleRenameRequest}
      onDelete={handleDeleteRequest}
    />
  );

  const handleNavigate = (event: NavigationEvent) => {
    if (event.type !== NavigationEventType.ITEM) {
      return;
    }
    handleBrowseItem(event.item as MountExplorerItem);
  };

  const clearActionItems = () => {
    setActionItems([]);
  };

  return {
    previewItem: mountPreviewController.previewItem,
    setPreviewCurrentItem: mountPreviewController.setPreviewCurrentItem,
    openPreview: mountPreviewController.openPreview,
    closePreview: mountPreviewController.closePreview,
    actionItems,
    activeActionItem,
    clearActionItems,
    selectionBarActions,
    getContextMenuItems,
    handleNavigate,
    handleFileClick: (item: MountExplorerItem) =>
      mountPreviewController.openPreview(item),
    handleCreateFolderSelection: (item: MountExplorerItem) =>
      selectSingleItem(item),
    handleRenameRequest,
    handleMoveRequest,
    handleDeleteRequest,
    handleRenameSuccess,
    handleMoveSuccess,
    handleDeleteSuccess,
  };
};
