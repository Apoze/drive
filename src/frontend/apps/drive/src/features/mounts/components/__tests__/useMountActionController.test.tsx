import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
} from "@/features/drivers/types";
import {
  getMountContextMenuActionIds,
  getMountSelectionBarActionIds,
} from "../mountActionControllerView";
import { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";

const buildMountItem = (
  overrides: Partial<MountExplorerItem> = {},
): MountExplorerItem => ({
  id: "mount-entry:mount-1:/file.txt",
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
  updated_at: new Date("2026-03-22T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-22T00:00:00Z"),
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
    mountTitle: "Shared Docs",
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

describe("useMountActionController helpers", () => {
  it("keeps multi-selection actions limited to delete and move", () => {
    const items = [
      buildMountItem(),
      buildMountItem({
        id: "mount-entry:mount-1:/other.txt",
        title: "other.txt",
        filename: "other.txt",
        path: "/other.txt",
        mountMeta: {
          mountId: "mount-1",
          normalizedPath: "/other.txt",
          entryType: "file",
          mountTitle: "Shared Docs",
          abilities: {
            children_list: false,
            create_folder: false,
            move: true,
            rename: true,
            destroy: true,
            upload: false,
            duplicate: false,
            download: true,
            preview: true,
            wopi: false,
            share_link_create: false,
          },
        },
      }),
    ];

    expect(getMountSelectionBarActionIds(items)).toEqual(["delete", "move"]);
  });

  it("keeps folder selection actions capability-driven", () => {
    const folder = buildMountItem({
      id: "mount-entry:mount-1:/folder",
      title: "folder",
      filename: "folder",
      type: ItemType.FOLDER,
      path: "/folder",
      url: undefined,
      mimetype: undefined,
      mountMeta: {
        mountId: "mount-1",
        normalizedPath: "/folder",
        entryType: "folder",
        mountTitle: "Shared Docs",
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

    expect(getMountSelectionBarActionIds([folder])).toEqual([
      "browse",
      "share",
      "rename",
      "move",
      "delete",
    ]);
  });

  it("keeps file selection actions capability-driven", () => {
    expect(getMountSelectionBarActionIds([buildMountItem()])).toEqual([
      "preview",
      "share",
      "download",
      "duplicate",
      "wopi",
      "rename",
      "move",
      "delete",
    ]);
  });

  it("keeps shared context actions aligned before info and delete", () => {
    expect(getMountContextMenuActionIds(buildMountItem())).toEqual([
      "preview",
      "share",
      "download",
      "duplicate",
      "wopi",
      "rename",
      "move",
      "separator",
      "view_info",
      "separator",
      "delete",
    ]);
  });

  it("keeps info as the only context action for a limited file", () => {
    const limitedFile = buildMountItem({
      url: undefined,
      mountMeta: {
        mountId: "mount-1",
        normalizedPath: "/file.txt",
        entryType: "file",
        mountTitle: "Shared Docs",
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

    expect(getMountContextMenuActionIds(limitedFile)).toEqual(["view_info"]);
  });
});
