import { getMountShellActionIds } from "../mountShellActions";

describe("getMountShellActionIds", () => {
  it("exposes import and create folder only when the current mount folder supports them", () => {
    expect(
      getMountShellActionIds({
        capabilities: {
          "mount.upload": true,
          "mount.create_folder": true,
        },
        entry: {
          entry_type: "folder",
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
      }),
    ).toEqual(["create_folder", "import_files", "import_folders"]);
  });

  it("fails closed when the current entry is not a folder", () => {
    expect(
      getMountShellActionIds({
        capabilities: {
          "mount.upload": true,
          "mount.create_folder": true,
        },
        entry: {
          entry_type: "file",
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
    ).toEqual([]);
  });

  it("does not overclaim actions when a capability or ability is missing", () => {
    expect(
      getMountShellActionIds({
        capabilities: {
          "mount.upload": true,
          "mount.create_folder": false,
        },
        entry: {
          entry_type: "folder",
          abilities: {
            children_list: true,
            create_folder: true,
            move: true,
            rename: true,
            destroy: true,
            upload: false,
            duplicate: false,
            download: false,
            preview: false,
            wopi: false,
            share_link_create: false,
          },
        },
      }),
    ).toEqual([]);
  });

  it("keeps folder import hidden when folder creation is unavailable", () => {
    expect(
      getMountShellActionIds({
        capabilities: {
          "mount.upload": true,
          "mount.create_folder": false,
        },
        entry: {
          entry_type: "folder",
          abilities: {
            children_list: true,
            create_folder: false,
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
      }),
    ).toEqual(["import_files"]);
  });
});
