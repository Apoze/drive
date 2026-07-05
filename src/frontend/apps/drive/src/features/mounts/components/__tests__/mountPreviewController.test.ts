import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
} from "@/features/drivers/types";
import type { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { createMountPreviewController } from "../mountPreviewController";

const buildMountItem = (
  preview: boolean,
): MountExplorerItem => ({
  id: preview ? "mount-entry:mount-1:/file.txt" : "mount-entry:mount-1:/folder",
  title: preview ? "file.txt" : "folder",
  filename: preview ? "file.txt" : "folder",
  creator: {
    id: "mount",
    full_name: "Mount",
    short_name: "MT",
  },
  type: preview ? ItemType.FILE : ItemType.FOLDER,
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: null,
  computed_link_role: null,
  upload_state: ItemUploadState.READY,
  updated_at: new Date("2026-03-22T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-22T00:00:00Z"),
  path: preview ? "/file.txt" : "/folder",
  url: preview ? "http://example.test/file" : undefined,
  mimetype: preview ? "text/plain" : undefined,
  link_reach: LinkReach.RESTRICTED,
  link_role: LinkRole.READER,
  abilities: {
    accesses_manage: false,
    accesses_view: false,
    children_create: false,
    children_list: false,
    destroy: false,
    favorite: false,
    invite_owner: false,
    link_configuration: false,
    media_auth: false,
    move: false,
    link_select_options: {
      [LinkReach.RESTRICTED]: null,
      [LinkReach.AUTHENTICATED]: null,
      [LinkReach.PUBLIC]: null,
    },
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: false,
    update: false,
    upload_ended: false,
  },
  mountMeta: {
    mountId: "mount-1",
    normalizedPath: preview ? "/file.txt" : "/folder",
    entryType: preview ? "file" : "folder",
    mountTitle: "Shared Docs",
    abilities: {
      children_list: false,
      create_folder: false,
      move: true,
      rename: true,
      destroy: true,
      upload: false,
      duplicate: false,
      download: preview,
      preview,
      wopi: false,
      share_link_create: false,
    },
  },
});

describe("mountPreviewController", () => {
  it("exposes explicit open and close operations for mount preview state", () => {
    const setPreviewCurrentItem = jest.fn();
    const previewItem = buildMountItem(true);
    const anotherPreviewItem = {
      ...buildMountItem(true),
      id: "mount-entry:mount-1:/other.txt",
      title: "other.txt",
      filename: "other.txt",
      path: "/other.txt",
      mountMeta: {
        ...buildMountItem(true).mountMeta,
        normalizedPath: "/other.txt",
      },
    };
    const controller = createMountPreviewController({
      previewItem,
      setPreviewCurrentItem,
    });

    controller.openPreview(previewItem);
    controller.openPreview(buildMountItem(false));
    controller.closePreviewIfCurrent(previewItem.id);
    controller.closePreviewIfIncluded([anotherPreviewItem, previewItem]);
    controller.closePreview();

    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(1, previewItem);
    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(2, undefined);
    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(3, undefined);
    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(4, undefined);
  });
});
