import React from "react";
import {
  buildItemImportMenuItems,
  ITEM_IMPORT_FILES_INPUT_ID,
  ITEM_IMPORT_FOLDERS_INPUT_ID,
  triggerItemImportInput,
} from "../itemImportMenuItems";

const asActionItem = (item: unknown) => {
  return item as {
    label: string;
    isHidden: boolean;
    icon: React.ReactElement<{ alt: string }>;
    callback?: () => void;
  };
};

const mockedGetElementById = jest.fn();

describe("itemImportMenuItems", () => {
  beforeEach(() => {
    mockedGetElementById.mockReset();
    Object.defineProperty(global, "document", {
      value: {
        getElementById: mockedGetElementById,
      },
      configurable: true,
    });
  });

  it("keeps the default import menu labels, ids and DOM click wiring", () => {
    const filesInput = {
      click: jest.fn(),
    };
    const foldersInput = {
      click: jest.fn(),
    };
    mockedGetElementById.mockImplementation((inputId: string) => {
      if (inputId === ITEM_IMPORT_FILES_INPUT_ID) {
        return filesInput;
      }
      if (inputId === ITEM_IMPORT_FOLDERS_INPUT_ID) {
        return foldersInput;
      }
      return null;
    });

    const items = buildItemImportMenuItems({
      t: (key) => key,
    });

    expect(ITEM_IMPORT_FILES_INPUT_ID).toBe("import-files");
    expect(ITEM_IMPORT_FOLDERS_INPUT_ID).toBe("import-folders");
    expect(items).toHaveLength(2);
    expect(asActionItem(items[0])).toMatchObject({
      label: "explorer.tree.import.files",
      isHidden: false,
    });
    expect(asActionItem(items[1])).toMatchObject({
      label: "explorer.tree.import.folders",
      isHidden: false,
    });
    expect(asActionItem(items[0]).icon.props.alt).toBe("");
    expect(asActionItem(items[1]).icon.props.alt).toBe("");

    asActionItem(items[0]).callback?.();
    asActionItem(items[1]).callback?.();

    expect(filesInput.click).toHaveBeenCalledTimes(1);
    expect(foldersInput.click).toHaveBeenCalledTimes(1);
  });

  it("keeps explicit hidden state and custom callbacks when provided", () => {
    const onImportFiles = jest.fn();
    const onImportFolders = jest.fn();

    const items = buildItemImportMenuItems({
      t: (key) => `translated:${key}`,
      isHidden: true,
      onImportFiles,
      onImportFolders,
    });

    expect(asActionItem(items[0])).toMatchObject({
      label: "translated:explorer.tree.import.files",
      isHidden: true,
    });
    expect(asActionItem(items[1])).toMatchObject({
      label: "translated:explorer.tree.import.folders",
      isHidden: true,
    });

    asActionItem(items[0]).callback?.();
    asActionItem(items[1]).callback?.();

    expect(onImportFiles).toHaveBeenCalledTimes(1);
    expect(onImportFolders).toHaveBeenCalledTimes(1);
  });

  it("ignores missing DOM inputs when triggering an import input directly", () => {
    mockedGetElementById.mockReturnValue(null);

    expect(() => triggerItemImportInput("missing-input")).not.toThrow();
  });
});
