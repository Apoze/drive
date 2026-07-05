import { getEventCoordinates } from "@dnd-kit/utilities";
import { Modifier } from "@dnd-kit/core";
import { TreeViewNodeTypeEnum } from "@gouvfr-lasuite/ui-kit";
import { Item, TreeItem } from "@/features/drivers/types";
import { DefaultRoute } from "@/utils/defaultRoutes";
import {
  canMountItemsDrop,
  isMountExplorerItem,
} from "@/features/mounts/utils/mountDnd";
import { getOriginalIdFromTreeId } from "./explorerTreeData";

export const snapToTopLeft: Modifier = ({
  activatorEvent,
  draggingNodeRect,
  transform,
}) => {
  if (draggingNodeRect && activatorEvent) {
    const activatorCoordinates = getEventCoordinates(activatorEvent);

    if (!activatorCoordinates) {
      return transform;
    }

    const offsetX = activatorCoordinates.x - draggingNodeRect.left;
    const offsetY = activatorCoordinates.y - draggingNodeRect.top;

    return {
      ...transform,
      x: transform.x + offsetX - 5,
      y: transform.y + offsetY - 5,
    };
  }

  return transform;
};

export const canDrop = (activeItem: Item, overItem: Item | TreeItem) => {
  if ("nodeType" in overItem) {
    if (overItem.nodeType !== TreeViewNodeTypeEnum.NODE) {
      return false;
    }
  }

  if (isMountExplorerItem(activeItem) && isMountExplorerItem(overItem as Item)) {
    return canMountItemsDrop(activeItem, overItem as Item);
  }

  const overItemId = overItem?.id
    ? getOriginalIdFromTreeId(overItem.id)
    : undefined;
  const activeItemId = getOriginalIdFromTreeId(activeItem.id);

  if (overItemId === DefaultRoute.FAVORITES) {
    return true;
  }
  if (activeItemId === overItemId) {
    return false;
  }

  const activePath = activeItem.path;
  const overPath = overItem.path;

  const canDropChildren = overItem.abilities?.children_create;
  const canMove = activeItem.abilities?.move;

  if (!canDropChildren || !canMove) {
    return false;
  }

  if (!activePath || !overPath) {
    return false;
  }

  const activePathSegments = activePath.split(".");
  const overPathSegments = overPath.split(".");

  if (overPath.startsWith(activePath)) {
    return false;
  }

  if (overPathSegments.length < 1) {
    return false;
  }

  const activePathWithoutLastSegment = activePathSegments
    .slice(0, -1)
    .join(".");

  if (activePathWithoutLastSegment === overPath) {
    return false;
  }

  return true;
};
