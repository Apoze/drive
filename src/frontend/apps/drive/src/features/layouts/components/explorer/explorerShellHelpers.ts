import { Item } from "@/features/drivers/types";
import { DefaultRoute, getDefaultRoute, ORDERED_DEFAULT_ROUTES } from "@/utils/defaultRoutes";
import { getMountRouteTreeSelectionId } from "@/features/mounts/utils/mountTree";

export const buildExplorerLayoutNavigateTarget = ({
  item,
  minimal,
}: {
  item: Pick<Item, "id"> & Partial<Pick<Item, "originalId">>;
  minimal?: string | string[];
}) => {
  const id = item.originalId ?? item.id;

  return {
    id,
    pathname: "/explorer/items/[id]",
    query: {
      id,
      ...(minimal ? { minimal } : {}),
    },
  };
};

export const resolveExplorerPanelsLayoutState = ({
  hasUser,
  isMinimalLayout,
}: {
  hasUser: boolean;
  isMinimalLayout?: boolean;
}) => ({
  showExplorerTree: hasUser,
  hideLeftPanelOnDesktop: !hasUser || Boolean(isMinimalLayout),
});

export const getExplorerTreeSelectedNodeId = ({
  pathname,
  mountId,
  path,
  itemId,
}: {
  pathname: string;
  mountId?: string;
  path?: string;
  itemId?: string;
}) => {
  const mountTreeNodeId = getMountRouteTreeSelectionId({
    pathname,
    mountId,
    path,
  });
  if (mountTreeNodeId) {
    return mountTreeNodeId;
  }

  const defaultRoute = getDefaultRoute(pathname);
  if (defaultRoute) {
    return defaultRoute.id;
  }

  return itemId;
};

export const getExplorerTreeDefaultRoutes = () =>
  ORDERED_DEFAULT_ROUTES.filter(
    (route) =>
      route.id !== DefaultRoute.FAVORITES && route.id !== DefaultRoute.MOUNTS,
  );

export type ExplorerTreeMoveDecision =
  | { kind: "noop" }
  | { kind: "direct" }
  | {
      kind: "confirm";
      sourceItem: Item;
      targetItem: Item;
    };

export const resolveExplorerTreeMoveDecision = ({
  sourceItem,
  parent,
  oldParent,
}: {
  sourceItem?: Item;
  parent?: Item;
  oldParent?: Item;
}): ExplorerTreeMoveDecision => {
  if (!sourceItem || !parent || !oldParent) {
    return { kind: "noop" };
  }

  const oldParentPath = oldParent.path.split(".");
  const parentPath = parent.path.split(".");

  if (parentPath[0] === oldParentPath[0]) {
    return { kind: "direct" };
  }

  return {
    kind: "confirm",
    sourceItem: oldParent,
    targetItem: parent,
  };
};
