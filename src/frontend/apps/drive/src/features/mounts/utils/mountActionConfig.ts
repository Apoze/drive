import { getMountExplorerMeta, MountExplorerItem } from "./mountExplorerItems";

export type MountActionId =
  | "browse"
  | "preview"
  | "download"
  | "duplicate"
  | "wopi"
  | "share"
  | "move"
  | "rename"
  | "delete"
  | "view_info";

export const getMountActionIds = (item: MountExplorerItem): MountActionId[] => {
  const meta = getMountExplorerMeta(item);

  if (meta.entryType === "folder") {
    const actions: MountActionId[] = ["browse"];
    if (meta.abilities?.share_link_create) {
      actions.push("share");
    }
    if (meta.abilities?.move) {
      actions.push("move");
    }
    if (meta.abilities?.rename) {
      actions.push("rename");
    }
    if (meta.abilities?.destroy) {
      actions.push("delete");
    }
    actions.push("view_info");
    return actions;
  }

  const actions: MountActionId[] = [];
  if (meta.abilities?.preview) {
    actions.push("preview");
  }
  if (item.url) {
    actions.push("download");
  }
  if (meta.abilities?.duplicate) {
    actions.push("duplicate");
  }
  if (meta.abilities?.wopi) {
    actions.push("wopi");
  }
  if (meta.abilities?.share_link_create) {
    actions.push("share");
  }
  if (meta.abilities?.move) {
    actions.push("move");
  }
  if (meta.abilities?.rename) {
    actions.push("rename");
  }
  if (meta.abilities?.destroy) {
    actions.push("delete");
  }
  actions.push("view_info");
  return actions;
};
