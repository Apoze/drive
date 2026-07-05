import React from "react";
import { errorToString } from "@/features/api/APIError";
import { BatchOperationError } from "@/features/errors/BatchOperationError";
import { Item, Role } from "@/features/drivers/types";
import {
  Button,
  Modal,
  ModalSize,
  useModal,
} from "@gouvfr-lasuite/cunningham-react";
import { useQueryClient } from "@tanstack/react-query";
import {
  HorizontalSeparator,
  useResponsive,
  useTreeContext,
} from "@gouvfr-lasuite/ui-kit";
import { Trans, useTranslation } from "react-i18next";
import { useMoveItems } from "@/features/explorer/api/useMoveItem";
import { addItemsMovedToast } from "../../toasts/addItemsMovedToast";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";
import { ExplorerTreeMoveConfirmationModal } from "../../tree/ExplorerTreeMoveConfirmationModal";
import { ExplorerCreateFolderModal } from "../ExplorerCreateFolderModal";
import {
  EmbeddedExplorer,
  useEmbeddedExplorer,
} from "@/features/explorer/components/embedded-explorer/EmbeddedExplorer";
import { AddFolderButton } from "./AddFolderButton";
import { useGlobalExplorer } from "../../GlobalExplorerContext";
import { useRef } from "react";
import { useItem } from "@/features/explorer/hooks/useQueries";
import {
  createFolderTargetEmbeddedExplorerProps,
  resolveCurrentFolderTarget,
} from "../folderTargetModalHelpers";

interface ExplorerMoveFolderProps {
  isOpen: boolean;
  onClose: () => void;
  initialFolderId?: string;
  itemsToMove: Item[];
}

export const ExplorerMoveFolder = ({
  isOpen,
  onClose,
  initialFolderId,
  itemsToMove,
}: ExplorerMoveFolderProps) => {
  const { isDesktop } = useResponsive();
  const isMoveToRoot = useRef(false);
  const {
    itemId: currentItemId,
    clearSelection,
    replaceSelection,
    closeRightPanelIfIncluded,
  } = useGlobalExplorer();
  const queryClient = useQueryClient();

  const { t } = useTranslation();
  const treeContext = useTreeContext<Item>();
  const moveItems = useMoveItems();
  const moveConfirmationModal = useModal();
  const createFolderModal = useModal();

  const imOwner = itemsToMove.every((item) => {
    return item.user_role === Role.OWNER;
  });

  const showMoveToRootButton =
    imOwner && itemsToMove.every((item) => item.path.split(".").length > 1);

  const itemsExplorer = useEmbeddedExplorer({
    ...createFolderTargetEmbeddedExplorerProps({
      initialFolderId,
      breadcrumbsRight: () => (
        <Button
          size="small"
          variant="tertiary"
          icon={<AddFolderButton />}
          onClick={createFolderModal.open}
        />
      ),
    }),
    itemsFilter: (items) => {
      const filteredItems = items.filter((itemFiltered) => {
        return !itemsToMove.some((i) => {
          return i.id === itemFiltered.id;
        });
      });

      return filteredItems;
    },
  });

  const { data: item } = useItem(itemsExplorer.currentItemId!, {
    enabled: !!itemsExplorer.currentItemId,
  });

  const onCloseModal = () => {
    onClose();
    itemsExplorer.clearSelection?.();
  };

  const moveTargetRequiresLoadedItem =
    !!itemsExplorer.currentItemId && itemsExplorer.selectedItems.length === 0;
  const moveActionDisabled =
    (!itemsExplorer.currentItemId && itemsExplorer.selectedItems.length === 0) ||
    (moveTargetRequiresLoadedItem && item === undefined);

  const getMoveData = () => {
    const ids = itemsToMove.map((item) => item.id);
    const pathSegments = itemsToMove[0].path.split(".");
    const oldParentId = pathSegments[pathSegments.length - 2];
    const oldRootParentId = pathSegments[0];
    const currentFolderTarget = resolveCurrentFolderTarget({
      currentItem: item,
      currentItemId: itemsExplorer.currentItemId,
      selectedItems: itemsExplorer.selectedItems,
    });
    const newParentId = currentFolderTarget.folderId;
    const newParentItem = currentFolderTarget.folderItem;

    const newRootId = newParentItem?.path.split(".")[0];
    return {
      ids,
      oldParentId,
      oldRootParentId,
      newParentId,
      newParentItem,
      newRootId,
    };
  };
  const syncTreeMove = (ids: string[], newParentId?: string) => {
    if (!newParentId) {
      return;
    }

    let childrenCount =
      treeContext?.treeData.getNode(newParentId)?.children?.length ?? 0;

    ids.forEach((id) => {
      treeContext?.treeData.moveNode(id, newParentId, childrenCount);
      childrenCount++;
    });
  };

  const refreshMovedItemQueries = (ids: string[]) => {
    if (!ids.includes(currentItemId)) {
      return;
    }

    queryClient.invalidateQueries({
      queryKey: ["items", currentItemId],
    });
    queryClient.invalidateQueries({
      queryKey: ["breadcrumb", currentItemId],
    });
  };

  const handleMove = async (
    ids: string[],
    newParentId: string | undefined,
    oldParentId: string,
  ) => {
    try {
      await moveItems.mutateAsync({
        ids: ids,
        parentId: newParentId,
        oldParentId: oldParentId,
      });
      isMoveToRoot.current = false;
      syncTreeMove(ids, newParentId);
      refreshMovedItemQueries(ids);
      closeRightPanelIfIncluded(ids);
      clearSelection();
      onCloseModal();
      addItemsMovedToast(ids.length);
    } catch (error) {
      isMoveToRoot.current = false;

      if (error instanceof BatchOperationError) {
        if (error.completedIds.length > 0) {
          syncTreeMove(error.completedIds, newParentId);
          refreshMovedItemQueries(error.completedIds);
          closeRightPanelIfIncluded(error.completedIds);
          replaceSelection(
            itemsToMove.filter(
              (itemToMove) => !error.completedIds.includes(itemToMove.id),
            ),
          );
          onCloseModal();
          addItemsMovedToast(error.completedIds.length);
        }

        const failedItem = itemsToMove.find(
          (itemToMove) => itemToMove.id === error.failedId,
        );
        addToast(
          <ToasterItem type="error">
            <span className="material-icons">arrow_forward</span>
            <span>
              {t("explorer.actions.move.partial_error", {
                count: error.completedIds.length,
                name: failedItem?.title ?? "",
                detail: errorToString(error.cause),
              })}
            </span>
          </ToasterItem>,
        );
        return;
      }

      addToast(
        <ToasterItem type="error">
          <span className="material-icons">arrow_forward</span>
          <span>
            {t("explorer.actions.move.toast_error", {
              count: ids.length,
            })}
          </span>
        </ToasterItem>,
      );
    }
  };

  const onMove = () => {
    // If we are in the root, and no item is selected, we can't move
    if (
      itemsExplorer.currentItemId === null &&
      itemsExplorer.selectedItems.length === 0
    ) {
      return;
    }

    // If we are in a folder, and the item is not found, we can't move
    if (itemsExplorer.currentItemId && item === undefined) {
      return;
    }
    const data = getMoveData();
    if (data.newRootId !== data.oldRootParentId) {
      moveConfirmationModal.open();
      return;
    }

    void handleMove(data.ids, data.newParentId, data.oldParentId);
  };

  const onMoveToRoot = () => {
    isMoveToRoot.current = true;
    moveConfirmationModal.open();
  };

  return (
    <>
      <Modal
        isOpen={isOpen}
        aria-label={t("explorer.modal.move.aria_label")}
        closeOnClickOutside
        title={
          <div className="modal__move__header">
            <span className="modal__move__title">
              {t("explorer.modal.move.title")}
            </span>
            <span className="modal__move__description">
              <Trans
                i18nKey={
                  itemsToMove.length === 1
                    ? "explorer.modal.move.description_one_item"
                    : "explorer.modal.move.description_multiple_items"
                }
                values={{
                  count: itemsToMove.length,
                  name: itemsToMove[0].title,
                }}
              />
            </span>
          </div>
        }
        onClose={onCloseModal}
        size={isDesktop ? ModalSize.MEDIUM : ModalSize.FULL}
        leftActions={
          <>
            {showMoveToRootButton && (
              <Button
                variant="tertiary"
                onClick={onMoveToRoot}
                className="move-to-root-button"
                fullWidth={true}
              >
                {t("explorer.modal.move.move_to_root")}
              </Button>
            )}
          </>
        }
        rightActions={
          <>
            <Button variant="tertiary" onClick={onCloseModal} fullWidth={true}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={moveActionDisabled}
              onClick={onMove}
              fullWidth={true}
            >
              {t("explorer.modal.move.move_button")}
            </Button>
          </>
        }
      >
        <div className="noPadding">
          <HorizontalSeparator withPadding={false} />
          <div className="modal__move__explorer">
            <EmbeddedExplorer {...itemsExplorer} showSearch={true} />
          </div>
          <HorizontalSeparator withPadding={false} />
        </div>
      </Modal>
      {createFolderModal.isOpen && (
        <ExplorerCreateFolderModal
          {...createFolderModal}
          parentId={itemsExplorer.currentItemId ?? undefined}
        />
      )}
      {moveConfirmationModal.isOpen && (
        <ExplorerTreeMoveConfirmationModal
          itemsCount={itemsToMove.length}
          isMoveToRoot={isMoveToRoot.current}
          isOpen={moveConfirmationModal.isOpen}
          onClose={() => {
            moveConfirmationModal.close();
            isMoveToRoot.current = false;
          }}
          sourceItem={itemsToMove[0]}
          targetItem={getMoveData().newParentItem!}
          onMove={() => {
            const data = getMoveData();

            if (isMoveToRoot.current) {
              void handleMove(data.ids, undefined, data.oldParentId);
            } else {
              void handleMove(data.ids, data.newParentId, data.oldParentId);
            }
            isMoveToRoot.current = false;
            moveConfirmationModal.close();
          }}
        />
      )}
    </>
  );
};
