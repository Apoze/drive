import { buildMountImportMenuItems } from "../mountImportMenuItems";

describe("buildMountImportMenuItems", () => {
  it("returns file and folder import actions when both capabilities are enabled", () => {
    const onImportFiles = jest.fn();
    const onImportFolders = jest.fn();

    const items = buildMountImportMenuItems({
      canUploadCurrentFolder: true,
      canImportFoldersCurrentFolder: true,
      onImportFiles,
      onImportFolders,
      t: (key) => key,
    });

    expect(items).toHaveLength(2);
    expect(items[0]).toEqual(
      expect.objectContaining({
        label: "explorer.tree.import.files",
        callback: onImportFiles,
      }),
    );
    expect(items[1]).toEqual(
      expect.objectContaining({
        label: "explorer.tree.import.folders",
        callback: onImportFolders,
      }),
    );
  });

  it("omits folder import when the capability is unavailable", () => {
    const items = buildMountImportMenuItems({
      canUploadCurrentFolder: true,
      canImportFoldersCurrentFolder: false,
      onImportFiles: jest.fn(),
      onImportFolders: jest.fn(),
      t: (key) => key,
    });

    expect(items).toHaveLength(1);
    expect(items[0]).toEqual(
      expect.objectContaining({
        label: "explorer.tree.import.files",
      }),
    );
  });
});
