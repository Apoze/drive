import { getMountActionIds } from "@/features/mounts/utils/mountActionConfig";
import { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";

export type MountActionControllerActionId =
  | "browse"
  | "preview"
  | "download"
  | "duplicate"
  | "wopi"
  | "share"
  | "move"
  | "rename"
  | "delete"
  | "view_info"
  | "separator";

const buildOrderedActionIds = ({
  availableIds,
  leadingIds,
  infoIds = [],
  dangerIds = [],
}: {
  availableIds: MountActionControllerActionId[];
  leadingIds: MountActionControllerActionId[];
  infoIds?: MountActionControllerActionId[];
  dangerIds?: MountActionControllerActionId[];
}): MountActionControllerActionId[] => {
  const ordered: MountActionControllerActionId[] = [];
  const hasAction = (actionId: MountActionControllerActionId) =>
    availableIds.includes(actionId);
  const appendSection = (actionIds: MountActionControllerActionId[]) => {
    const visibleIds = actionIds.filter(hasAction);
    if (visibleIds.length === 0) {
      return;
    }
    if (ordered.length > 0) {
      ordered.push("separator");
    }
    ordered.push(...visibleIds);
  };

  ordered.push(...leadingIds.filter(hasAction));
  appendSection(infoIds);
  appendSection(dangerIds);
  return ordered;
};

const getMountLeadingActionIds = (
  item: MountExplorerItem,
): MountActionControllerActionId[] => {
  const baseActionIds = getMountActionIds(item);

  if (item.mountMeta.entryType === "folder") {
    const folderActionIds = [
      "browse",
      "share",
      "rename",
      "move",
    ] satisfies MountActionControllerActionId[];
    return folderActionIds.filter((actionId) =>
      baseActionIds.includes(actionId),
    ) as MountActionControllerActionId[];
  }

  const fileActionIds = [
    "preview",
    "share",
    "download",
    "duplicate",
    "wopi",
    "rename",
    "move",
  ] satisfies MountActionControllerActionId[];
  return fileActionIds.filter((actionId) =>
    baseActionIds.includes(actionId),
  ) as MountActionControllerActionId[];
};

export const getMountSelectionBarActionIds = (
  selectedItems: MountExplorerItem[],
): MountActionControllerActionId[] => {
  if (selectedItems.length === 0) {
    return [];
  }

  if (selectedItems.length > 1) {
    return ["delete", "move"];
  }

  return buildOrderedActionIds({
    availableIds: getMountActionIds(selectedItems[0]),
    leadingIds: getMountLeadingActionIds(selectedItems[0]),
    dangerIds: ["delete"],
  }).filter((actionId) => actionId !== "separator");
};

export const getMountContextMenuActionIds = (
  item: MountExplorerItem,
): MountActionControllerActionId[] => {
  return buildOrderedActionIds({
    availableIds: getMountActionIds(item),
    leadingIds: getMountLeadingActionIds(item),
    infoIds: ["view_info"],
    dangerIds: ["delete"],
  });
};
