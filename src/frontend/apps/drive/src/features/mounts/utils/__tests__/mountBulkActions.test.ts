import { ItemType, ItemUploadState, LinkReach, LinkRole } from "@/features/drivers/types";
import {
  getMountBulkSelectionState,
  getParentMountPath,
  isSameOrDescendantMountPath,
  resolveMountMovePreflight,
  sortMountItemsForDelete,
} from "../mountBulkActions";
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

describe("mountBulkActions", () => {
  it("computes bulk selection abilities conservatively", () => {
    const items = [
      buildMountItem(),
      buildMountItem({
        id: "mount-entry:test:/folder",
        title: "folder",
        filename: "folder",
        type: ItemType.FOLDER,
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
      }),
    ];

    expect(getMountBulkSelectionState(items)).toEqual({
      count: 2,
      sameMount: true,
      canDelete: true,
      canMove: true,
    });
  });

  it("rejects move preflight when the selection spans multiple mounts", () => {
    const first = buildMountItem();
    const second = buildMountItem({
      id: "mount-entry:test:/other.txt",
      title: "other.txt",
      filename: "other.txt",
      path: "/other.txt",
      mountMeta: {
        ...buildMountItem().mountMeta,
        mountId: "mount-2",
        normalizedPath: "/other.txt",
      },
    });

    expect(
      resolveMountMovePreflight({
        items: [first, second],
        targetPath: "/target",
        destinationEntries: [],
      }),
    ).toEqual({ ok: false, code: "mixed_mount" });
  });

  it("rejects moving a folder into itself or one of its descendants", () => {
    const folder = buildMountItem({
      id: "mount-entry:test:/projects",
      title: "projects",
      filename: "projects",
      type: ItemType.FOLDER,
      path: "/projects",
      url: undefined,
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

    expect(
      resolveMountMovePreflight({
        items: [folder],
        targetPath: "/projects/nested",
        destinationEntries: [],
      }),
    ).toEqual({ ok: false, code: "invalid_destination" });
  });

  it("rejects move preflight when the selection would collide on the target", () => {
    const first = buildMountItem({
      id: "mount-entry:test:/a/report.txt",
      path: "/a/report.txt",
      mountMeta: {
        ...buildMountItem().mountMeta,
        normalizedPath: "/a/report.txt",
      },
    });
    const second = buildMountItem({
      id: "mount-entry:test:/b/report.txt",
      path: "/b/report.txt",
      mountMeta: {
        ...buildMountItem().mountMeta,
        normalizedPath: "/b/report.txt",
      },
    });

    expect(
      resolveMountMovePreflight({
        items: [first, second],
        targetPath: "/archive",
        destinationEntries: [],
      }),
    ).toEqual({
      ok: false,
      code: "target_conflict",
      conflictingName: "report.txt",
    });
  });

  it("accepts noop targets while still rejecting real destination collisions", () => {
    const alreadyThere = buildMountItem({
      id: "mount-entry:test:/archive/report.txt",
      path: "/archive/report.txt",
      mountMeta: {
        ...buildMountItem().mountMeta,
        normalizedPath: "/archive/report.txt",
      },
    });
    const other = buildMountItem({
      id: "mount-entry:test:/incoming/notes.txt",
      title: "notes.txt",
      filename: "notes.txt",
      path: "/incoming/notes.txt",
      mountMeta: {
        ...buildMountItem().mountMeta,
        normalizedPath: "/incoming/notes.txt",
      },
    });

    expect(
      resolveMountMovePreflight({
        items: [alreadyThere, other],
        targetPath: "/archive",
        destinationEntries: [
          {
            mount_id: "mount-1",
            normalized_path: "/archive/report.txt",
            entry_type: "file",
            name: "report.txt",
            abilities: buildMountItem().mountMeta.abilities!,
          },
        ],
      }),
    ).toEqual({ ok: true });
  });

  it("sorts delete targets from deepest path to shallowest", () => {
    const sorted = sortMountItemsForDelete([
      buildMountItem({
        id: "1",
        path: "/z",
        mountMeta: { ...buildMountItem().mountMeta, normalizedPath: "/z" },
      }),
      buildMountItem({
        id: "2",
        path: "/a/b",
        mountMeta: { ...buildMountItem().mountMeta, normalizedPath: "/a/b" },
      }),
      buildMountItem({
        id: "3",
        path: "/a",
        mountMeta: { ...buildMountItem().mountMeta, normalizedPath: "/a" },
      }),
    ]);

    expect(sorted.map((item) => item.mountMeta.normalizedPath)).toEqual([
      "/a/b",
      "/a",
      "/z",
    ]);
  });

  it("keeps mount path helpers deterministic", () => {
    expect(getParentMountPath("/")).toBeNull();
    expect(getParentMountPath("/projects")).toBe("/");
    expect(getParentMountPath("/projects/nested")).toBe("/projects");
    expect(isSameOrDescendantMountPath("/projects", "/projects")).toBe(true);
    expect(isSameOrDescendantMountPath("/projects", "/projects/nested")).toBe(true);
    expect(isSameOrDescendantMountPath("/projects", "/archive")).toBe(false);
  });
});
