import {
  ItemType,
  MountDiscovery,
  MountVirtualEntry,
  TreeItem,
} from "@/features/drivers/types";
import { DefaultRoute } from "@/utils/defaultRoutes";
import {
  discoveryToMountExplorerItem,
  entryToMountExplorerItem,
  MountExplorerItem,
} from "./mountExplorerItems";
import { getParentMountPath } from "./mountBulkActions";
import { TreeViewDataType, TreeViewNodeTypeEnum } from "@gouvfr-lasuite/ui-kit";

const MOUNT_ROOT_PREFIX = "mount-root:";
const MOUNT_ENTRY_PREFIX = "mount-entry:";
const MOUNT_TREE_FOLDER_CHILDREN_SENTINEL = 1;

export const isMountsTreeRootId = (treeId: string) => {
  return treeId === DefaultRoute.MOUNTS;
};

export const isMountTreeNodeId = (treeId: string) => {
  return (
    isMountsTreeRootId(treeId) ||
    treeId.startsWith(MOUNT_ROOT_PREFIX) ||
    treeId.startsWith(MOUNT_ENTRY_PREFIX)
  );
};

export const isMountTreeItem = (item: unknown): item is MountExplorerItem => {
  return typeof item === "object" && item !== null && "mountMeta" in item;
};

export const getMountTreeNodeId = (mountId: string, normalizedPath: string) => {
  if (!normalizedPath || normalizedPath === "/") {
    return `${MOUNT_ROOT_PREFIX}${mountId}`;
  }
  return `${MOUNT_ENTRY_PREFIX}${mountId}:${normalizedPath}`;
};

export const getMountTreeParentNodeId = (
  mountId: string,
  normalizedPath: string,
) => {
  return getMountTreeNodeId(mountId, getParentMountPath(normalizedPath) || "/");
};

export const parseMountTreeNodeId = (
  treeId: string,
): { mountId: string; normalizedPath: string } | null => {
  if (treeId.startsWith(MOUNT_ROOT_PREFIX)) {
    return {
      mountId: treeId.slice(MOUNT_ROOT_PREFIX.length),
      normalizedPath: "/",
    };
  }

  if (!treeId.startsWith(MOUNT_ENTRY_PREFIX)) {
    return null;
  }

  const encoded = treeId.slice(MOUNT_ENTRY_PREFIX.length);
  const separatorIndex = encoded.indexOf(":");
  if (separatorIndex < 0) {
    return null;
  }

  const mountId = encoded.slice(0, separatorIndex);
  const normalizedPath = encoded.slice(separatorIndex + 1) || "/";
  return { mountId, normalizedPath };
};

export const buildMountsTreeRoot = (
  label: string,
  childrenCount: number,
): TreeViewDataType<TreeItem> => {
  return {
    id: DefaultRoute.MOUNTS,
    nodeType: TreeViewNodeTypeEnum.SIMPLE_NODE,
    label,
    childrenCount,
    children: [],
  };
};

export const mountExplorerItemToTreeItem = (
  item: MountExplorerItem,
  parentId: string,
): TreeItem => {
  const canListChildren =
    item.type === ItemType.FOLDER && Boolean(item.abilities.children_list);

  return {
    ...item,
    id: getMountTreeNodeId(item.mountMeta.mountId, item.mountMeta.normalizedPath),
    originalId: item.id,
    parentId,
    childrenCount: canListChildren ? MOUNT_TREE_FOLDER_CHILDREN_SENTINEL : 0,
    children: [],
    nodeType: TreeViewNodeTypeEnum.NODE,
    title: item.title,
  };
};

export const discoveryToMountTreeItem = (mount: MountDiscovery): TreeItem => {
  return mountExplorerItemToTreeItem(
    discoveryToMountExplorerItem(mount),
    DefaultRoute.MOUNTS,
  );
};

export const entryToMountTreeItem = ({
  mountId,
  entry,
  mountTitle,
  provider,
  parentId,
}: {
  mountId: string;
  entry: MountVirtualEntry;
  mountTitle: string;
  provider?: string;
  parentId: string;
}): TreeItem => {
  return mountExplorerItemToTreeItem(
    entryToMountExplorerItem(mountId, entry, mountTitle, provider),
    parentId,
  );
};

export const getMountRouteTreeSelectionId = ({
  pathname,
  mountId,
  path,
}: {
  pathname: string;
  mountId?: string;
  path?: string;
}) => {
  if (pathname === "/explorer/mounts") {
    return DefaultRoute.MOUNTS;
  }

  if (!mountId) {
    return undefined;
  }

  if (pathname === "/explorer/mounts/[mount_id]") {
    return getMountTreeNodeId(mountId, path || "/");
  }

  if (
    pathname === "/explorer/mounts/[mount_id]/preview" ||
    pathname === "/explorer/mounts/[mount_id]/wopi"
  ) {
    return getMountTreeNodeId(mountId, getParentMountPath(path || "/") || "/");
  }

  return undefined;
};
