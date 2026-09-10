import { TreeViewNodeTypeEnum } from "@gouvfr-lasuite/ui-kit";
import { Item, TreeItem } from "@/features/drivers/types";
import { itemToTreeItem } from "@/features/explorer/components/explorerTreeData";
import {
  discoveryToMountExplorerItem,
  getMountExplorerMeta,
} from "@/features/mounts/utils/mountExplorerItems";
import {
  StoragePage,
  StorageResource,
  StorageSpace,
  resourceItem,
  storageRequest,
  getResource,
  resolveLegacyMount,
} from "./api";

export const SPACES_TREE_ROOT = "storage-spaces";
export const resourceTreeId = (id: string, space: string) =>
  `resource:${space}::${id}`;
export const parseResourceTreeId = (value: string) => {
  const match = /^resource:([0-9a-f-]{36})::([0-9a-f-]{36})$/i.exec(value);
  return match ? { space: match[1], id: match[2] } : undefined;
};
export const resolveExplorerResource = async (item: Item) => {
  const node = parseResourceTreeId(item.id);
  if (node) return getResource(node.id, node.space);
  const meta = getMountExplorerMeta(item);
  if (meta) {
    const location = await resolveLegacyMount(
      meta.mountId,
      meta.normalizedPath,
    );
    return getResource(location.id, location.space);
  }
  return getResource(item.originalId ?? item.id);
};
export const resourceTreeItem = (resource: StorageResource): TreeItem => ({
  ...itemToTreeItem(resourceItem(resource)),
  id: resourceTreeId(resource.id, resource.space),
  originalId: resource.id,
  childrenCount: resource.kind === "folder" ? 1 : 0,
});
export const spacesTreeRoot = (label: string): TreeItem => ({
  id: SPACES_TREE_ROOT,
  label,
  nodeType: TreeViewNodeTypeEnum.SIMPLE_NODE,
  childrenCount: 1,
  children: [],
});
export const loadSpaceRoots = async (page = 1) => {
  const spaces = await storageRequest<StoragePage<StorageSpace>>("spaces/", {
    params: { offset: (page - 1) * 50, limit: 50 },
  });
  return {
    children: spaces.results.flatMap((space) =>
      space.roots.map((root) => {
        const item = itemToTreeItem(
          discoveryToMountExplorerItem({
            mount_id: space.id,
            display_name:
              space.roots.length > 1
                ? `${space.name} — ${root.title}`
                : space.name,
            provider: "virtual",
            capabilities: {},
          }),
        );
        return {
          ...item,
          id: resourceTreeId(root.id, space.id),
          originalId: root.id,
          abilities: { ...item.abilities, ...root.abilities },
          childrenCount: 1,
        };
      }),
    ),
    pagination: {
      currentPage: page,
      totalCount: spaces.count,
      hasMore: Boolean(spaces.next),
    },
  };
};
export const loadResourceTreeChildren = async (
  id: string,
  space: string,
  page = 1,
) => {
  const children = await storageRequest<StoragePage<StorageResource>>(
    `resources/${id}/children/`,
    {
      params: { space, offset: (page - 1) * 50, limit: 50 },
    },
  );
  return {
    children: children.results.map(resourceTreeItem),
    pagination: {
      currentPage: page,
      totalCount: children.count,
      hasMore: Boolean(children.next),
    },
  };
};
