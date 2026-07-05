import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
} from "@/features/drivers/types";
import { getMountActionIds } from "../mountActionConfig";
import { MountExplorerItem } from "../mountExplorerItems";

const buildMountItem = (
  overrides: Partial<MountExplorerItem> = {},
): MountExplorerItem => ({
  id: "mount-entry:test:/file.txt",
  title: "file.txt",
  filename: "file.txt",
  creator: {
    id: "mount",
    full_name: "Mount",
    short_name: "MT",
  },
  type: ItemType.FILE,
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: null,
  computed_link_role: null,
  upload_state: ItemUploadState.READY,
  updated_at: new Date("2026-03-21T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-21T00:00:00Z"),
  path: "/file.txt",
  url: "http://example.test/download",
  mimetype: "text/plain",
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
    normalizedPath: "/file.txt",
    entryType: "file",
    mountTitle: "SMB",
    abilities: {
      children_list: false,
      create_folder: false,
      move: true,
      rename: true,
      destroy: true,
      upload: false,
      duplicate: true,
      download: true,
      preview: true,
      wopi: true,
      share_link_create: true,
    },
  },
  ...overrides,
});

describe("getMountActionIds", () => {
  it("keeps folder actions capability-driven and exposes delete only when supported", () => {
    const folder = buildMountItem({
      type: ItemType.FOLDER,
      title: "folder",
      filename: "folder",
      path: "/folder",
      url: undefined,
      mountMeta: {
        mountId: "mount-1",
        normalizedPath: "/folder",
        entryType: "folder",
        mountTitle: "SMB",
        abilities: {
          children_list: true,
          create_folder: true,
          move: true,
          rename: true,
          destroy: true,
          upload: true,
          duplicate: false,
          download: false,
          preview: false,
          wopi: false,
          share_link_create: true,
        },
      },
    });

    expect(getMountActionIds(folder)).toEqual([
      "browse",
      "share",
      "move",
      "rename",
      "delete",
      "view_info",
    ]);
  });

  it("keeps file actions capability-driven and always exposes info last", () => {
    expect(getMountActionIds(buildMountItem())).toEqual([
      "preview",
      "download",
      "duplicate",
      "wopi",
      "share",
      "move",
      "rename",
      "delete",
      "view_info",
    ]);
  });

  it("does not claim unsupported file actions", () => {
    const limitedFile = buildMountItem({
      url: undefined,
      mountMeta: {
        mountId: "mount-1",
        normalizedPath: "/file.txt",
        entryType: "file",
        mountTitle: "SMB",
        abilities: {
          children_list: false,
          create_folder: false,
          move: false,
          rename: false,
          destroy: false,
          upload: false,
          duplicate: false,
          download: false,
          preview: false,
          wopi: false,
          share_link_create: false,
        },
      },
    });

    expect(getMountActionIds(limitedFile)).toEqual(["view_info"]);
  });
});
