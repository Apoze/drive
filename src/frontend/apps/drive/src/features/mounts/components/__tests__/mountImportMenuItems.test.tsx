import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { buildMountImportMenuItems } from "../mountImportMenuItems";

const getActionItem = (item: ReturnType<typeof buildMountImportMenuItems>[number]) =>
  item as {
    label: string;
    icon: React.ReactNode;
    callback?: () => void;
  };

describe("buildMountImportMenuItems", () => {
  const t = (key: string) => key;

  it("returns only the files import item when only file upload is allowed", () => {
    const onImportFiles = jest.fn();
    const onImportFolders = jest.fn();

    const items = buildMountImportMenuItems({
      canUploadCurrentFolder: true,
      canImportFoldersCurrentFolder: false,
      onImportFiles,
      onImportFolders,
      t,
    });

    expect(items).toHaveLength(1);
    const action = getActionItem(items[0]);
    expect(action.label).toBe("explorer.tree.import.files");
    expect(renderToStaticMarkup(action.icon as React.ReactElement)).toContain(
      "upload_file",
    );
    action.callback?.();
    expect(onImportFiles).toHaveBeenCalledTimes(1);
    expect(onImportFolders).not.toHaveBeenCalled();
  });

  it("returns only the folders import item when only folder import is allowed", () => {
    const onImportFiles = jest.fn();
    const onImportFolders = jest.fn();

    const items = buildMountImportMenuItems({
      canUploadCurrentFolder: false,
      canImportFoldersCurrentFolder: true,
      onImportFiles,
      onImportFolders,
      t,
    });

    expect(items).toHaveLength(1);
    const action = getActionItem(items[0]);
    expect(action.label).toBe("explorer.tree.import.folders");
    expect(renderToStaticMarkup(action.icon as React.ReactElement)).toContain(
      "drive_folder_upload",
    );
    action.callback?.();
    expect(onImportFolders).toHaveBeenCalledTimes(1);
    expect(onImportFiles).not.toHaveBeenCalled();
  });

  it("returns both items in stable order when both capabilities are allowed", () => {
    const items = buildMountImportMenuItems({
      canUploadCurrentFolder: true,
      canImportFoldersCurrentFolder: true,
      onImportFiles: jest.fn(),
      onImportFolders: jest.fn(),
      t,
    });

    expect(items.map((item) => getActionItem(item).label)).toEqual([
      "explorer.tree.import.files",
      "explorer.tree.import.folders",
    ]);
  });

  it("returns no item when import capabilities are absent", () => {
    const items = buildMountImportMenuItems({
      canUploadCurrentFolder: false,
      canImportFoldersCurrentFolder: false,
      onImportFiles: jest.fn(),
      onImportFolders: jest.fn(),
      t,
    });

    expect(items).toEqual([]);
  });
});
