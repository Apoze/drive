import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { useGlobalExplorer } from "../GlobalExplorerContext";
import { Item, TreeItem } from "@/features/drivers/types";
import {
  HorizontalSeparator,
  IconSize,
  OpenMap,
  TreeDataItem,
  TreeView,
  TreeViewDataType,
  TreeViewMoveResult,
  TreeViewNodeTypeEnum,
  useTreeContext,
} from "@gouvfr-lasuite/ui-kit";
import { useEffect, useMemo, useState } from "react";
import { ExplorerTreeItem } from "./ExplorerTreeItem";
import { useMoveItems } from "../../api/useMoveItem";
import { ExplorerTreeActions } from "./ExplorerTreeActions";
import { ExplorerTreeNav } from "./nav/ExplorerTreeNav";
import { addItemsMovedToast } from "../toasts/addItemsMovedToast";
import { ExplorerTreeMoveConfirmationModal } from "./ExplorerTreeMoveConfirmationModal";
import { canDrop } from "../ExplorerDndProvider";
import React from "react";
import { LeftPanelMobile } from "@/features/layouts/components/left-panel/LeftPanelMobile";
import { useAuth } from "@/features/auth/Auth";
import { ExplorerTreeNavItem } from "./nav/ExplorerTreeNavItem";
import { useRouter } from "next/router";
import {
  getMountTreeNodeId,
  entryToMountTreeItem,
  isMountTreeItem,
  isMountsTreeRootId,
} from "@/features/mounts/utils/mountTree";
import { getDriver } from "@/features/config/Config";
import { useQueryClient } from "@tanstack/react-query";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";
import { errorToString } from "@/features/api/APIError";
import { BatchOperationError } from "@/features/errors/BatchOperationError";
import {
  getExplorerTreeDefaultRoutes,
  getExplorerTreeSelectedNodeId,
  resolveExplorerTreeMoveDecision,
} from "@/features/layouts/components/explorer/explorerShellHelpers";

export const ExplorerTree = () => {
  const move = useMoveItems();
  const moveConfirmationModal = useModal();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const [moveState, setMoveState] = useState<{
    moveCallback: () => void;
    sourceItem: Item;
    targetItem: Item;
  }>();

  const treeContext = useTreeContext<TreeItem>();
  const [initialOpenState, setInitialOpenState] = useState<OpenMap | undefined>(
    undefined,
  );

  const { itemId, treeIsInitialized } = useGlobalExplorer();
  const defaultSelectedNodeId = useMemo(() => {
    return getExplorerTreeSelectedNodeId({
      pathname: router.pathname,
      mountId:
        typeof router.query.mount_id === "string" ? router.query.mount_id : undefined,
      path: typeof router.query.path === "string" ? router.query.path : undefined,
      itemId,
    });
  }, [itemId, router.pathname, router.query.mount_id, router.query.path]);

  // Initialize the opened nodes when the tree is initialized.
  useEffect(() => {
    if (!treeIsInitialized) {
      return;
    }
    if (initialOpenState) {
      return;
    }
    const initialOpenedNodes: OpenMap = {};

    // Browse the data to initialize the opened nodes
    const openLoadedNodes = (
      items: TreeDataItem<TreeViewDataType<TreeItem>>[],
    ) => {
      items.forEach((item) => {
        if (
          item.value.childrenCount &&
          item.value.childrenCount > 0 &&
          item.value.children &&
          item.value.children.length > 0
        ) {
          initialOpenedNodes[item.value.id] = true;

          if (item.value.children) {
            openLoadedNodes(item.children!);
          }
        }
      });
    };

    const treeData = treeContext!.treeData.nodes;
    openLoadedNodes(treeData);
    setInitialOpenState(initialOpenedNodes);
  }, [treeContext?.treeData.nodes]);

  const handleMove = (result: TreeViewMoveResult) => {
    const sourceItem = treeContext?.treeData.getNode(result.sourceId) as Item | undefined;
    const targetItem = result.targetModeId
      ? (treeContext?.treeData.getNode(result.targetModeId) as Item | undefined)
      : undefined;

    if (
      sourceItem &&
      targetItem &&
      isMountTreeItem(sourceItem) &&
      isMountTreeItem(targetItem)
    ) {
      return;
    }

    move.mutate(
      {
        ids: [result.sourceId],
        parentId: result.targetModeId,
        oldParentId: result.oldParentId ?? itemId,
      },
      {
        onSuccess: () => {
          addItemsMovedToast(1);
        },
        onError: (error) => {
          addToast(
            <ToasterItem type="error">
              {error instanceof BatchOperationError
                ? t("explorer.actions.move.partial_error", {
                    count: error.completedIds.length,
                    name: sourceItem?.title ?? "",
                    detail: errorToString(error.cause),
                  })
                : t("explorer.actions.move.toast_error", { count: 1 })}
            </ToasterItem>,
          );
        },
      },
    );
  };

  const handleMountTreeMove = async ({
    sourceItem,
    targetItem,
  }: {
    sourceItem: Item;
    targetItem: Item;
  }) => {
    if (!isMountTreeItem(sourceItem) || !isMountTreeItem(targetItem)) {
      return;
    }

    try {
      const movedEntry = await getDriver().moveMountEntry({
        mountId: sourceItem.mountMeta.mountId,
        path: sourceItem.mountMeta.normalizedPath,
        targetPath: targetItem.mountMeta.normalizedPath,
      });

      treeContext?.treeData.deleteNode(
        getMountTreeNodeId(
          sourceItem.mountMeta.mountId,
          sourceItem.mountMeta.normalizedPath,
        ),
      );
      treeContext?.treeData.addChild(
        getMountTreeNodeId(
          targetItem.mountMeta.mountId,
          targetItem.mountMeta.normalizedPath,
        ),
        entryToMountTreeItem({
          mountId: sourceItem.mountMeta.mountId,
          entry: movedEntry,
          mountTitle: sourceItem.mountMeta.mountTitle,
          provider: sourceItem.mountMeta.provider,
          parentId: getMountTreeNodeId(
            targetItem.mountMeta.mountId,
            targetItem.mountMeta.normalizedPath,
          ),
        }),
      );

      addItemsMovedToast(1);
      await queryClient.invalidateQueries({
        queryKey: ["mounts", "browse", sourceItem.mountMeta.mountId],
      });
    } catch (error) {
      addToast(
        <ToasterItem type="error">
          {t("explorer.mounts.bulk.move.partial_error", {
            count: 0,
            name: sourceItem.title,
            detail: errorToString(error),
          })}
        </ToasterItem>,
      );
      await queryClient.invalidateQueries({
        queryKey: ["mounts", "browse", sourceItem.mountMeta.mountId],
      });
    }
  };

  return (
    <div className="explorer__tree">
      <ExplorerTreeActions />
      <HorizontalSeparator withPadding={false} />
      <ExplorerTreeNavDefault />
      
      {initialOpenState && (
        <TreeView
          selectedNodeId={defaultSelectedNodeId}
          afterMove={handleMove}
          beforeMove={(moveResult, moveCallback) => {
            // TODO: this comes from the tree in the ui-kit, it needs to be explained in the documentation
            if (!moveResult.newParentId || !moveResult.oldParentId) {
              return;
            }

            const parent = treeContext?.treeData.getNode(
              moveResult.newParentId,
            ) as Item | undefined;
            const oldParent = treeContext?.treeData.getNode(
              moveResult.oldParentId,
            ) as Item | undefined;
            const sourceItem = treeContext?.treeData.getNode(
              moveResult.sourceId,
            ) as Item | undefined;

            if (!parent || !oldParent || !sourceItem) {
              return;
            }

            if (isMountTreeItem(sourceItem) || isMountTreeItem(parent)) {
              void handleMountTreeMove({
                sourceItem,
                targetItem: parent,
              });
              return;
            }

            const decision = resolveExplorerTreeMoveDecision({
              sourceItem,
              parent,
              oldParent,
            });

            if (decision.kind === "noop") {
              return;
            }

            if (decision.kind === "direct") {
              moveCallback();
              return;
            }

            setMoveState({
              moveCallback,
              sourceItem: decision.sourceItem,
              targetItem: decision.targetItem,
            });
            moveConfirmationModal.open();
          }}
          canDrag={(args) => {
            const item = args.value as TreeItem;
            if (item.nodeType !== TreeViewNodeTypeEnum.NODE) {
              return false;
            }

            return item.abilities?.move ?? false;
          }}
          paddingTop={0}
          canDrop={(args) => {
            const parent = args.parentNode?.data.value as Item | undefined;
            const activeItem = args.dragNodes[0].data.value as Item;
            if (args.parentNode && isMountsTreeRootId(args.parentNode.id)) {
              return false;
            }

            const canDropResult = parent ? canDrop(activeItem, parent) : true;

            const result =
              args.index === 0 &&
              args.parentNode?.willReceiveDrop === true &&
              canDropResult;

            return result;
          }}
          renderNode={ExplorerTreeItem}
          rootNodeId={"root"}
        />
      )}
      <ExplorerTreeNav />
      <div className="explorer__tree__mobile-navs">
        <HorizontalSeparator />
        <LeftPanelMobile />
      </div>
      {moveState && moveConfirmationModal.isOpen && (
        <ExplorerTreeMoveConfirmationModal
          isOpen={moveConfirmationModal.isOpen}
          onClose={() => {
            moveConfirmationModal.close();
            setMoveState(undefined);
          }}
          sourceItem={moveState.sourceItem}
          targetItem={moveState.targetItem}
          onMove={() => {
            moveState.moveCallback();
            moveConfirmationModal.close();
          }}
        />
      )}
    </div>
  );
};

export const ExplorerTreeNavDefault = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const nodes = useMemo(() => {
    if (!user) {
      return [];
    }

    return getExplorerTreeDefaultRoutes().map((route) => ({
      id: route.id,
      label: t(route.label),
      route: route.route,
      icon: <route.icon size={IconSize.SMALL} />,
    }));
  }, [user, t]);

  if (!nodes) {
    return null;
  }

  return (
    <div className="explorer__tree__nav">
      {nodes.map((node) => (
        <ExplorerTreeNavItem key={node.id} {...node} />
      ))}
    </div>
  );
};
