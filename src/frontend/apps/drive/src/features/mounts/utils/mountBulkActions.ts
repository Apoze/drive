import { MountVirtualEntry } from "@/features/drivers/types";
import { MountExplorerItem } from "./mountExplorerItems";

export type MountBulkSelectionState = {
  count: number;
  sameMount: boolean;
  canDelete: boolean;
  canMove: boolean;
};

export type MountMovePreflightCode =
  | "mixed_mount"
  | "unsupported_selection"
  | "invalid_destination"
  | "target_conflict";

export type MountMovePreflightResult =
  | {
      ok: true;
    }
  | {
      ok: false;
      code: MountMovePreflightCode;
      conflictingName?: string;
    };

const getMountItemName = (item: MountExplorerItem) => {
  const path = item.mountMeta.normalizedPath;
  const segments = path.split("/").filter(Boolean);
  return segments[segments.length - 1] ?? item.title;
};

export const isSameOrDescendantMountPath = (
  parentPath: string,
  candidatePath: string,
) => {
  if (candidatePath === parentPath) {
    return true;
  }
  if (parentPath === "/") {
    return candidatePath.startsWith("/");
  }
  return candidatePath.startsWith(`${parentPath.replace(/\/$/, "")}/`);
};

export const getParentMountPath = (path: string) => {
  if (!path || path === "/") {
    return null;
  }
  const segments = path.split("/").filter(Boolean);
  if (segments.length <= 1) {
    return "/";
  }
  return `/${segments.slice(0, -1).join("/")}`;
};

export const getMountBulkSelectionState = (
  items: MountExplorerItem[],
): MountBulkSelectionState => {
  const mountIds = new Set(items.map((item) => item.mountMeta.mountId));
  return {
    count: items.length,
    sameMount: mountIds.size <= 1,
    canDelete: items.length > 0 && items.every((item) => item.mountMeta.abilities?.destroy),
    canMove: items.length > 0 && items.every((item) => item.mountMeta.abilities?.move),
  };
};

export const sortMountItemsForDelete = (items: MountExplorerItem[]) => {
  return [...items].sort((left, right) => {
    const leftDepth = left.mountMeta.normalizedPath.split("/").filter(Boolean).length;
    const rightDepth = right.mountMeta.normalizedPath.split("/").filter(Boolean).length;
    if (leftDepth !== rightDepth) {
      return rightDepth - leftDepth;
    }
    return left.mountMeta.normalizedPath.localeCompare(right.mountMeta.normalizedPath);
  });
};

export const resolveMountMovePreflight = ({
  items,
  targetPath,
  destinationEntries,
}: {
  items: MountExplorerItem[];
  targetPath: string;
  destinationEntries: MountVirtualEntry[];
}): MountMovePreflightResult => {
  const selection = getMountBulkSelectionState(items);
  if (!selection.sameMount) {
    return { ok: false, code: "mixed_mount" };
  }
  if (!selection.canMove) {
    return { ok: false, code: "unsupported_selection" };
  }

  const destinationPaths = new Set(
    destinationEntries.map((entry) => entry.normalized_path),
  );
  const plannedTargets = new Map<string, string>();

  for (const item of items) {
    if (
      item.mountMeta.entryType === "folder" &&
      isSameOrDescendantMountPath(item.mountMeta.normalizedPath, targetPath)
    ) {
      return { ok: false, code: "invalid_destination" };
    }

    const finalPath =
      targetPath === "/"
        ? `/${getMountItemName(item)}`
        : `${targetPath.replace(/\/$/, "")}/${getMountItemName(item)}`;

    const duplicate = plannedTargets.get(finalPath);
    if (duplicate && duplicate !== item.id) {
      return {
        ok: false,
        code: "target_conflict",
        conflictingName: getMountItemName(item),
      };
    }
    plannedTargets.set(finalPath, item.id);

    if (finalPath !== item.mountMeta.normalizedPath && destinationPaths.has(finalPath)) {
      return {
        ok: false,
        code: "target_conflict",
        conflictingName: getMountItemName(item),
      };
    }
  }

  return { ok: true };
};
