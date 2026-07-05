import { ItemType, ItemUploadState, LinkReach, LinkRole } from "@/features/drivers/types";
import {
  canMountItemReceiveDrop,
  canMountItemsDrop,
  isMountExplorerItem,
} from "../mountDnd";
import { MountExplorerItem } from "../mountExplorerItems";
import { discoveryToMountExplorerItem } from "../mountExplorerItems";

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
    move: true,
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
      share_link_create: false,
    },
  },
  ...overrides,
});

describe("mountDnd", () => {
  it("detects mount explorer items", () => {
    expect(isMountExplorerItem(buildMountItem())).toBe(true);
  });

  it("marks only browseable folders as drop targets", () => {
    const folder = buildMountItem({
      id: "mount-entry:test:/folder",
      title: "folder",
      filename: "folder",
      type: ItemType.FOLDER,
      path: "/folder",
      url: undefined,
      abilities: {
        ...buildMountItem().abilities,
        children_list: true,
      },
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
          share_link_create: false,
        },
      },
    });

    expect(canMountItemReceiveDrop(folder)).toBe(true);
    expect(canMountItemReceiveDrop(buildMountItem())).toBe(false);
    expect(
      canMountItemReceiveDrop(
        discoveryToMountExplorerItem({
          mount_id: "mount-1",
          display_name: "Finance",
          provider: "smb",
          capabilities: {},
        }),
      ),
    ).toBe(true);
  });

  it("accepts an intra-mount file drop onto another folder", () => {
    const file = buildMountItem();
    const targetFolder = buildMountItem({
      id: "mount-entry:test:/archive",
      title: "archive",
      filename: "archive",
      type: ItemType.FOLDER,
      path: "/archive",
      url: undefined,
      abilities: {
        ...buildMountItem().abilities,
        children_list: true,
      },
      mountMeta: {
        mountId: "mount-1",
        normalizedPath: "/archive",
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
          share_link_create: false,
        },
      },
    });

    expect(canMountItemsDrop(file, targetFolder)).toBe(true);
  });

  it("rejects cross-mount drops", () => {
    const file = buildMountItem();
    const targetFolder = buildMountItem({
      id: "mount-entry:test:/archive",
      title: "archive",
      filename: "archive",
      type: ItemType.FOLDER,
      path: "/archive",
      url: undefined,
      abilities: {
        ...buildMountItem().abilities,
        children_list: true,
      },
      mountMeta: {
        mountId: "mount-2",
        normalizedPath: "/archive",
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
          share_link_create: false,
        },
      },
    });

    expect(canMountItemsDrop(file, targetFolder)).toBe(false);
  });

  it("rejects dropping a folder into itself or a descendant", () => {
    const folder = buildMountItem({
      id: "mount-entry:test:/projects",
      title: "projects",
      filename: "projects",
      type: ItemType.FOLDER,
      path: "/projects",
      url: undefined,
      abilities: {
        ...buildMountItem().abilities,
        children_list: true,
      },
      mountMeta: {
        mountId: "mount-1",
        normalizedPath: "/projects",
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
          share_link_create: false,
        },
      },
    });
    const descendant = buildMountItem({
      id: "mount-entry:test:/projects/nested",
      title: "nested",
      filename: "nested",
      type: ItemType.FOLDER,
      path: "/projects/nested",
      url: undefined,
      abilities: {
        ...buildMountItem().abilities,
        children_list: true,
      },
      mountMeta: {
        mountId: "mount-1",
        normalizedPath: "/projects/nested",
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
          share_link_create: false,
        },
      },
    });

    expect(canMountItemsDrop(folder, folder)).toBe(false);
    expect(canMountItemsDrop(folder, descendant)).toBe(false);
  });
});
