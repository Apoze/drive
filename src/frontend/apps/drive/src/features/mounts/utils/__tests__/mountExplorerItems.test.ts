import {
  ItemType,
  MountDiscovery,
  MountVirtualEntry,
} from "@/features/drivers/types";
import {
  discoveryToMountExplorerItem,
  entryToMountExplorerItem,
  getMountExplorerMeta,
  getMountTitle,
} from "../mountExplorerItems";

jest.mock("@/features/api/utils", () => ({
  getOrigin: () => "http://api.test",
}));

describe("mountExplorerItems", () => {
  it("prefers display names and uses provider-agnostic fallbacks", () => {
    expect(
      getMountTitle({
        mount_id: "finance",
        provider: "smb",
        display_name: "Finance share",
      } as MountDiscovery),
    ).toBe("Finance share");

    expect(
      getMountTitle({
        mount_id: "local-mount",
        provider: "localfs",
        display_name: "",
      } as MountDiscovery),
    ).toBe("local-mount");

    expect(
      getMountTitle({
        mount_id: "shared-docs",
        provider: "localfs",
        display_name: "Shared Docs",
      } as MountDiscovery),
    ).toBe("Shared Docs");
  });

  it("does not use provider-branded display names as public mount titles", () => {
    expect(
      getMountTitle({
        mount_id: "smb-1",
        provider: "smb",
        display_name: "SMB",
      } as MountDiscovery),
    ).toBe("smb-1");

    expect(
      getMountTitle({
        mount_id: "smb",
        provider: "smb",
        display_name: "SMB",
      } as MountDiscovery),
    ).toBe("Mount");
  });

  it("maps a discovery entry to a mount root explorer item", () => {
    const item = discoveryToMountExplorerItem({
      mount_id: "mount-1",
      display_name: "Shared Docs",
      provider: "localfs",
      capabilities: {},
    });

    expect(item).toMatchObject({
      id: "mount-root:mount-1",
      title: "Shared Docs",
      filename: "Shared Docs",
      type: ItemType.FOLDER,
      abilities: expect.objectContaining({
        children_create: false,
        children_list: true,
        retrieve: true,
      }),
      mountMeta: {
        mountId: "mount-1",
        normalizedPath: "/",
        entryType: "folder",
        mountTitle: "Shared Docs",
        provider: "localfs",
        isMountRoot: true,
      },
    });
  });

  it("maps file entries with inferred mime type and canonical download/preview urls", () => {
    const entry: MountVirtualEntry = {
      mount_id: "mount-1",
      normalized_path: "/Reports/April notes.JPG",
      entry_type: "file",
      name: "April notes.JPG",
      size: 1234,
      modified_at: "2026-03-30T12:00:00Z",
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
        wopi: false,
        share_link_create: true,
      },
    };

    const item = entryToMountExplorerItem(
      "mount-1",
      entry,
      "Shared Docs",
      "localfs",
    );

    expect(item).toMatchObject({
      id: "mount-entry:mount-1:/Reports/April notes.JPG",
      title: "April notes.JPG",
      filename: "April notes.JPG",
      type: ItemType.FILE,
      size: 1234,
      mimetype: "image/jpeg",
      url:
        "http://api.test/api/v1.0/mounts/mount-1/download/?path=%2FReports%2FApril+notes.JPG",
      url_preview:
        "http://api.test/api/v1.0/mounts/mount-1/preview/?path=%2FReports%2FApril+notes.JPG",
      abilities: expect.objectContaining({
        retrieve: true,
        move: true,
        destroy: true,
        update: true,
      }),
      mountMeta: expect.objectContaining({
        mountId: "mount-1",
        normalizedPath: "/Reports/April notes.JPG",
        entryType: "file",
        mountTitle: "Shared Docs",
        provider: "localfs",
      }),
    });
  });

  it("maps folder entries without file-only metadata and exposes mount meta unchanged", () => {
    const entry: MountVirtualEntry = {
      mount_id: "mount-1",
      normalized_path: "/Projects",
      entry_type: "folder",
      name: "Projects",
      modified_at: null,
      abilities: {
        children_list: true,
        create_folder: true,
        move: true,
        rename: false,
        destroy: false,
        upload: true,
        duplicate: false,
        download: false,
        preview: false,
        wopi: false,
        share_link_create: false,
      },
    };

    const item = entryToMountExplorerItem("mount-1", entry, "Shared Docs");

    expect(item).toMatchObject({
      type: ItemType.FOLDER,
      url: undefined,
      url_preview: undefined,
      mimetype: undefined,
      abilities: expect.objectContaining({
        children_create: true,
        children_list: true,
        retrieve: true,
        update: false,
      }),
    });
    expect(getMountExplorerMeta(item)).toEqual({
      mountId: "mount-1",
      normalizedPath: "/Projects",
      entryType: "folder",
      mountTitle: "Shared Docs",
      provider: undefined,
      abilities: entry.abilities,
    });
  });

  it("falls back to octet-stream when a file extension is unknown", () => {
    const entry: MountVirtualEntry = {
      mount_id: "mount-1",
      normalized_path: "/blob.custom",
      entry_type: "file",
      name: "blob.custom",
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
    };

    const item = entryToMountExplorerItem("mount-1", entry, "Shared Docs");

    expect(item.mimetype).toBe("application/octet-stream");
    expect(item.abilities).toMatchObject({
      retrieve: false,
      move: false,
      destroy: false,
      update: false,
    });
  });
});
