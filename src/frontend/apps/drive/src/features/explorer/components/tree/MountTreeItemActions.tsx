import { Button, useModal } from "@gouvfr-lasuite/cunningham-react";
import { DropdownMenu, MenuItem } from "@gouvfr-lasuite/ui-kit";
import clsx from "clsx";
import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useRouter } from "next/router";
import { useQueryClient } from "@tanstack/react-query";
import { useTreeContext } from "@gouvfr-lasuite/ui-kit";
import { useGlobalExplorer } from "../GlobalExplorerContext";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { setFromRoute } from "../../utils/utils";
import { MountExplorerItem, entryToMountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { MountMoveModal } from "@/features/mounts/components/MountMoveModal";
import { MountRenameModal } from "@/features/mounts/components/MountRenameModal";
import { MountDeleteModal } from "@/features/mounts/components/MountDeleteModal";
import {
  entryToMountTreeItem,
  getMountTreeNodeId,
  getMountTreeParentNodeId,
} from "@/features/mounts/utils/mountTree";
import { getParentMountPath } from "@/features/mounts/utils/mountBulkActions";
import { TreeItem } from "@/features/drivers/types";
import { createAndCopyMountShareLink } from "@/features/mounts/utils/mountShareLink";
import { getMountContextMenuActionIds } from "@/features/mounts/components/mountActionControllerView";

export const MountTreeItemActions = ({ item }: { item: MountExplorerItem }) => {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const treeContext = useTreeContext<TreeItem>();
  const [isOpen, setIsOpen] = useState(false);
  const moveModal = useModal();
  const renameModal = useModal();
  const deleteModal = useModal();
  const {
    openRightPanelForItem,
    replaceRightPanelItemIfCurrent,
    closeRightPanelIfCurrent,
  } = useGlobalExplorer();

  const contextActionIds = getMountContextMenuActionIds(item);

  const replaceTreeNode = ({
    sourceItem,
    entry,
  }: {
    sourceItem: MountExplorerItem;
    entry: Parameters<typeof entryToMountExplorerItem>[1];
  }) => {
    const sourceTreeId = getMountTreeNodeId(
      sourceItem.mountMeta.mountId,
      sourceItem.mountMeta.normalizedPath,
    );
    const parentTreeId = getMountTreeParentNodeId(
      sourceItem.mountMeta.mountId,
      entry.normalized_path,
    );
    treeContext?.treeData.deleteNode(sourceTreeId);
    if (!treeContext?.treeData.getNode(parentTreeId)) {
      return;
    }
    treeContext?.treeData.addChild(
      parentTreeId,
      entryToMountTreeItem({
        mountId: sourceItem.mountMeta.mountId,
        entry,
        mountTitle: sourceItem.mountMeta.mountTitle,
        provider: sourceItem.mountMeta.provider,
        parentId: parentTreeId,
      }),
    );
  };

  const invalidateMountBrowse = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["mounts", "browse", item.mountMeta.mountId],
    });
  };

  const handleBrowse = () => {
    setFromRoute(DefaultRoute.MOUNTS);
    void router.push({
      pathname: "/explorer/mounts/[mount_id]",
      query: {
        mount_id: item.mountMeta.mountId,
        path: item.mountMeta.normalizedPath,
      },
    });
  };

  const handleShowInfo = () => {
    openRightPanelForItem(item);
  };

  const handleShare = async () => {
    await createAndCopyMountShareLink(item);
  };

  const handleRenameSuccess = async (
    entry: Parameters<typeof entryToMountExplorerItem>[1],
  ) => {
    replaceTreeNode({ sourceItem: item, entry });
    replaceRightPanelItemIfCurrent(
      item.id,
      entryToMountExplorerItem(
        item.mountMeta.mountId,
        entry,
        item.mountMeta.mountTitle,
        item.mountMeta.provider,
      ),
    );
    await invalidateMountBrowse();
  };

  const handleMoveSuccess = async (payload: {
    sourceItems: MountExplorerItem[];
    movedEntries: Parameters<typeof entryToMountExplorerItem>[1][];
  }) => {
    const movedEntry = payload.movedEntries[0];
    if (!movedEntry) {
      return;
    }
    replaceTreeNode({ sourceItem: item, entry: movedEntry });
    replaceRightPanelItemIfCurrent(
      item.id,
      entryToMountExplorerItem(
        item.mountMeta.mountId,
        movedEntry,
        item.mountMeta.mountTitle,
        item.mountMeta.provider,
      ),
    );
    await invalidateMountBrowse();
  };

  const handleDeleteSuccess = async () => {
    treeContext?.treeData.deleteNode(
      getMountTreeNodeId(item.mountMeta.mountId, item.mountMeta.normalizedPath),
    );
    closeRightPanelIfCurrent(item.id);
    await invalidateMountBrowse();
  };

  const actionItems: Partial<Record<string, MenuItem>> = {
    browse: {
      icon: <span className="material-icons">folder_open</span>,
      label: t("explorer.mounts.browse"),
      callback: handleBrowse,
    },
    share: {
      icon: <span className="material-icons">share</span>,
      label: t("explorer.mounts.actions.share"),
      callback: () => void handleShare(),
    },
    rename: {
      icon: <span className="material-icons">edit</span>,
      label: t("explorer.item.actions.rename"),
      callback: renameModal.open,
    },
    move: {
      icon: <span className="material-icons">drive_file_move</span>,
      label: t("explorer.item.actions.move"),
      callback: moveModal.open,
    },
    view_info: {
      icon: <span className="material-icons">info</span>,
      label: t("explorer.item.actions.view_info"),
      callback: handleShowInfo,
    },
    delete: {
      icon: <span className="material-icons">delete</span>,
      label: t("explorer.item.actions.delete"),
      variant: "danger" as const,
      callback: deleteModal.open,
    },
    separator: { type: "separator" as const },
  };
  const menuItems = contextActionIds
    .map((actionId) => actionItems[actionId])
    .filter((menuItem): menuItem is MenuItem => Boolean(menuItem));

  return (
    <>
      <div
        className={clsx("explorer__tree__item__actions", {
          "explorer__tree__item__actions--open": isOpen,
        })}
      >
        <DropdownMenu options={menuItems} isOpen={isOpen} onOpenChange={setIsOpen}>
          <Button
            size="nano"
            variant="tertiary"
            onClick={() => setIsOpen(!isOpen)}
            aria-label="more_actions"
            className="explorer__tree__item__actions__button-more"
            icon={<span className="material-icons more">more_horiz</span>}
          />
        </DropdownMenu>
      </div>
      {renameModal.isOpen && (
        <MountRenameModal
          isOpen={renameModal.isOpen}
          onClose={renameModal.close}
          item={item}
          onSuccess={(entry) => {
            void handleRenameSuccess(entry);
            renameModal.close();
          }}
        />
      )}
      {moveModal.isOpen && (
        <MountMoveModal
          isOpen={moveModal.isOpen}
          onClose={moveModal.close}
          items={[item]}
          initialDestinationPath={getParentMountPath(item.mountMeta.normalizedPath) || "/"}
          onSuccess={(payload) => {
            void handleMoveSuccess(payload);
            moveModal.close();
          }}
        />
      )}
      {deleteModal.isOpen && (
        <MountDeleteModal
          isOpen={deleteModal.isOpen}
          onClose={deleteModal.close}
          items={[item]}
          onSuccess={() => {
            void handleDeleteSuccess();
            deleteModal.close();
          }}
        />
      )}
    </>
  );
};
