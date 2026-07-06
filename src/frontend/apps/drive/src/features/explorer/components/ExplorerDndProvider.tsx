import React from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { useMoveItems } from "../api/useMoveItem";
import {
  useGlobalExplorer,
  getOriginalIdFromTreeId,
} from "./GlobalExplorerContext";
import { Item, TreeItem } from "@/features/drivers/types";
import { ExplorerDragOverlay } from "./tree/ExploreDragOverlay";
import { useTreeContext } from "@gouvfr-lasuite/ui-kit";
import { addItemsMovedToast } from "./toasts/addItemsMovedToast";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { createContext, useContext, useState } from "react";
import {
  ConfirmationMoveState,
  ExplorerTreeMoveConfirmationModal,
} from "./tree/ExplorerTreeMoveConfirmationModal";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { useMutationCreateFavoriteItem } from "../hooks/useMutations";
import { useQueryClient } from "@tanstack/react-query";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";
import { useTranslation } from "react-i18next";
import { errorToString } from "@/features/api/APIError";
import { BatchOperationError } from "@/features/errors/BatchOperationError";
import { getDriver } from "@/features/config/Config";
import { handleFavoriteCommand } from "./itemActionCommands";
import {
  isMountExplorerItem,
} from "@/features/mounts/utils/mountDnd";
import { getMountBulkSelectionState } from "@/features/mounts/utils/mountBulkActions";
import {
  entryToMountTreeItem,
  getMountTreeNodeId,
} from "@/features/mounts/utils/mountTree";
import {
  canDrop,
  snapToTopLeft,
} from "./explorerDndRuntime";
import {
  useSelectionCount,
  useSelectionStore,
} from "../stores/selectionStore";

export { canDrop, snapToTopLeft } from "./explorerDndRuntime";

const activationConstraint = {
  distance: 20,
};

type ExplorerDndProviderProps = {
  children: React.ReactNode;
};

type DndContextType = {
  overedItemIds: Record<string, boolean>;
  setOveredItemIds: React.Dispatch<
    React.SetStateAction<Record<string, boolean>>
  >;
};

const DragItemContext = createContext<DndContextType | undefined>(undefined);

export const useDragItemContext = () => {
  const context = useContext(DragItemContext);
  if (!context) {
    throw new Error("useDndContext must be used within an ExplorerDndProvider");
  }
  return context;
};

export const useOptionalDragItemContext = () => {
  return useContext(DragItemContext);
};

export const ExplorerDndProvider = ({ children }: ExplorerDndProviderProps) => {
  const moveConfirmationModal = useModal();
  const [overedItemIds, setOveredItemIds] = useState<Record<string, boolean>>(
    {},
  );
  const [moveState, setMoveState] = useState<ConfirmationMoveState | undefined>(
    undefined,
  );
  const {
    itemId,
    closePreview,
    clearRightPanelItem,
    closeRightPanel,
    clearSelection,
    replaceSelection,
    closeRightPanelIfIncluded,
    selectSingleItem,
  } = useGlobalExplorer();
  const selectionStore = useSelectionStore();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { mutateAsync: createFavoriteItem } = useMutationCreateFavoriteItem();

  const treeContext = useTreeContext<TreeItem>();

  const moveItems = useMoveItems();
  const mouseSensor = useSensor(MouseSensor, {
    activationConstraint,
  });

  const touchSensor = useSensor(TouchSensor, {
    activationConstraint,
  });
  const keyboardSensor = useSensor(KeyboardSensor, {});

  const sensors = useSensors(mouseSensor, touchSensor, keyboardSensor);
  const handleCreateFavoriteItem = async (item: Item) => {
    await handleFavoriteCommand({
      createFavoriteItem,
      effectiveItemId: item.id,
      item,
      addFavoriteChild: (itemTree) => {
        treeContext?.treeData.addChild(DefaultRoute.FAVORITES, itemTree);
      },
    });
  };

  const getDraggedItems = (activeItem: Item) => {
    const selectedItems = selectionStore.getSelectedItems();
    if (
      selectedItems.length > 0 &&
      selectedItems.some((item) => item.id === activeItem.id)
    ) {
      return selectedItems;
    }
    return [activeItem];
  };

  const clearMountMoveUiState = () => {
    clearSelection();
    closePreview();
    clearRightPanelItem();
    closeRightPanel();
    setOveredItemIds({});
  };

  const syncMountTreeMove = ({
    sourceItem,
    movedEntry,
    targetItem,
  }: {
    sourceItem: Item;
    movedEntry: Awaited<ReturnType<ReturnType<typeof getDriver>["moveMountEntry"]>>;
    targetItem: Item;
  }) => {
    if (
      !isMountExplorerItem(sourceItem) ||
      !isMountExplorerItem(targetItem) ||
      sourceItem.mountMeta.entryType !== "folder"
    ) {
      return;
    }

    const sourceTreeId = getMountTreeNodeId(
      sourceItem.mountMeta.mountId,
      sourceItem.mountMeta.normalizedPath,
    );
    const targetTreeId = getMountTreeNodeId(
      targetItem.mountMeta.mountId,
      targetItem.mountMeta.normalizedPath,
    );

    const sourceNode = treeContext?.treeData.getNode(sourceTreeId);
    const targetNode = treeContext?.treeData.getNode(targetTreeId);

    if (sourceNode) {
      treeContext?.treeData.deleteNode(sourceTreeId);
    }

    if (!targetNode) {
      return;
    }

    treeContext?.treeData.addChild(
      targetTreeId,
      entryToMountTreeItem({
        mountId: sourceItem.mountMeta.mountId,
        entry: movedEntry,
        mountTitle: sourceItem.mountMeta.mountTitle,
        provider: sourceItem.mountMeta.provider,
        parentId: targetTreeId,
      }),
    );
  };

  const handleMountMove = async ({
    activeItem,
    overItem,
  }: {
    activeItem: Item;
    overItem: Item;
  }) => {
    if (!isMountExplorerItem(activeItem) || !isMountExplorerItem(overItem)) {
      return;
    }

    const draggedItems = getDraggedItems(activeItem).filter(isMountExplorerItem);
    const selection = getMountBulkSelectionState(draggedItems);
    const movedItems: Item[] = [];

    if (!selection.sameMount) {
      addToast(
        <ToasterItem type="error">{t("explorer.mounts.bulk.move.mixed_mount")}</ToasterItem>,
      );
      setOveredItemIds({});
      return;
    }

    if (!selection.canMove) {
      addToast(
        <ToasterItem type="error">
          {t("explorer.mounts.bulk.move.unsupported_selection")}
        </ToasterItem>,
      );
      setOveredItemIds({});
      return;
    }

    try {
      for (const item of draggedItems) {
        const movedEntry = await getDriver().moveMountEntry({
          mountId: item.mountMeta.mountId,
          path: item.mountMeta.normalizedPath,
          targetPath: overItem.mountMeta.normalizedPath,
        });
        movedItems.push(item);
        syncMountTreeMove({
          sourceItem: item,
          movedEntry,
          targetItem: overItem,
        });
      }
      addItemsMovedToast(draggedItems.length);
    } catch (error) {
      if (movedItems.length > 0) {
        addItemsMovedToast(movedItems.length);
      }
      addToast(
        <ToasterItem type="error">
          {t("explorer.mounts.bulk.move.partial_error", {
            count: movedItems.length,
            name: draggedItems[movedItems.length]?.title ?? activeItem.title,
            detail: errorToString(error),
          })}
        </ToasterItem>,
      );
    } finally {
      clearMountMoveUiState();
      await queryClient.invalidateQueries({
        queryKey: ["mounts", "browse", activeItem.mountMeta.mountId],
      });
    }
  };

  const handleDragStart = (ev: DragStartEvent) => {
    document.body.style.cursor = "grabbing";
    const item = ev.active.data.current?.item as Item;
    if (!item) {
      return;
    }

    if (selectionStore.getSelectedItems().length > 0) {
      return;
    }

    selectSingleItem(item);
  };

  const moveTreeNodes = (ids: string[], newParentId: string) => {
    ids.forEach((id) => {
      treeContext?.treeData.moveNode(id, newParentId, 0);
    });
  };

  const handleMoveConfirmation = async ({
    draggedItems,
    newParentId,
  }: {
    draggedItems: Item[];
    newParentId: string;
  }) => {
    setOveredItemIds({});
    const ids = draggedItems.map((item) => item.id);
    try {
      await moveItems.mutateAsync({
        ids: ids,
        parentId: newParentId,
        oldParentId: itemId,
      });
      moveTreeNodes(ids, newParentId);
      closeRightPanelIfIncluded(ids);
      addItemsMovedToast(ids.length);
      clearSelection();
    } catch (error) {
      if (error instanceof BatchOperationError) {
        if (error.completedIds.length > 0) {
          moveTreeNodes(error.completedIds, newParentId);
          closeRightPanelIfIncluded(error.completedIds);
          addItemsMovedToast(error.completedIds.length);
        }
        replaceSelection(
          draggedItems.filter(
            (draggedItem) => !error.completedIds.includes(draggedItem.id),
          ),
        );
        const failedItem = draggedItems.find(
          (draggedItem) => draggedItem.id === error.failedId,
        );
        addToast(
          <ToasterItem type="error">
            {t("explorer.actions.move.partial_error", {
              count: error.completedIds.length,
              name: failedItem?.title ?? "",
              detail: errorToString(error.cause),
            })}
          </ToasterItem>,
        );
        return;
      }

      addToast(
        <ToasterItem type="error">
          {t("explorer.actions.move.toast_error", {
            count: ids.length,
          })}
        </ToasterItem>,
      );
    }
  };

  const handleDragEnd = async ({ active, over }: DragEndEvent) => {
    document.body.style.cursor = "default";

    const activeItemRaw = active.data.current?.item as Item;
    const overItemRaw = over?.data.current?.item as Item;

    // Extract the original item ID from the tree ID (handles favorites path format)
    const activeItem = {
      ...activeItemRaw,
      id: getOriginalIdFromTreeId(activeItemRaw.id),
    };
    const overItemId = overItemRaw?.id
      ? getOriginalIdFromTreeId(overItemRaw.id)
      : undefined;

    if (overItemId === DefaultRoute.FAVORITES && activeItem) {
      await handleCreateFavoriteItem(activeItem);
      return;
    }

    if (!activeItem || !overItemRaw || !overItemId) {
      return;
    }

    const overItem = { ...overItemRaw, id: overItemId };

    if (activeItem.id === overItem.id) {
      return;
    }

    const canDropResult = canDrop(activeItem, overItem);

    if (!canDropResult) {
      return;
    }

    if (isMountExplorerItem(activeItem) || isMountExplorerItem(overItem)) {
      if (!(isMountExplorerItem(activeItem) && isMountExplorerItem(overItem))) {
        return;
      }
      await handleMountMove({ activeItem, overItem });
      return;
    }

    const pathActiveItemSegments = activeItem.path.split(".");
    const pathOverItemSegments = overItem.path.split(".");

    if (pathActiveItemSegments[0] !== pathOverItemSegments[0]) {
      setMoveState({
        sourceItem: activeItem,
        targetItem: overItem,
      });
      setOveredItemIds({});
      moveConfirmationModal.open();
      return;
    }

    await handleMoveConfirmation({
      draggedItems: getDraggedItems(activeItem),
      newParentId: overItem.id,
    });
  };

  return (
    <>
      <DndContext
        sensors={sensors}
        modifiers={[snapToTopLeft]}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <DragOverlay dropAnimation={null}>
          <SelectionCountDragOverlay />
        </DragOverlay>
        <DragItemContext.Provider
          value={{
            overedItemIds,
            setOveredItemIds,
          }}
        >
          {children}
        </DragItemContext.Provider>
      </DndContext>
      {moveState && moveConfirmationModal.isOpen && (
        <ExplorerTreeMoveConfirmationModalWithCount
          isOpen={moveConfirmationModal.isOpen}
          onClose={() => {
            moveConfirmationModal.close();
            setMoveState(undefined);
          }}
          sourceItem={moveState.sourceItem}
          targetItem={moveState.targetItem}
          onMove={() => {
            void handleMoveConfirmation({
              draggedItems: getDraggedItems(moveState.sourceItem),
              newParentId: moveState.targetItem.id,
            });
            moveConfirmationModal.close();
          }}
        />
      )}
    </>
  );
};

const SelectionCountDragOverlay = () => {
  const count = useSelectionCount();
  return <ExplorerDragOverlay count={count} />;
};

const ExplorerTreeMoveConfirmationModalWithCount = (
  props: Omit<
    React.ComponentProps<typeof ExplorerTreeMoveConfirmationModal>,
    "itemsCount"
  >,
) => {
  const count = useSelectionCount();
  return <ExplorerTreeMoveConfirmationModal {...props} itemsCount={count} />;
};
