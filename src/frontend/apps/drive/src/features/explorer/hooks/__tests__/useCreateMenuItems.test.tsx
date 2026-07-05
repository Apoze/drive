import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useCreateMenuItems } from "../useCreateMenuItems";
import { useGlobalExplorer } from "../../components/GlobalExplorerContext";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  useModal: jest.fn(),
}));

jest.mock("../../components/GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("../../components/modals/ExplorerCreateFolderModal", () => ({
  ExplorerCreateFolderModal: () => null,
}));

jest.mock("../../components/modals/ExplorerCreateFileModal", () => ({
  ExplorerCreateFileModal: () => null,
  ExplorerCreateFileType: {
    DOC: "doc",
    CALC: "calc",
    POWERPOINT: "powerpoint",
  },
}));

jest.mock("../../components/icons/ItemIcon", () => ({
  ItemIcon: () => <span>item-icon</span>,
}));

const mockedUseModal = jest.mocked(useModal);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);

describe("useCreateMenuItems", () => {
  beforeEach(() => {
    mockedUseModal.mockReset();
    mockedUseModal
      .mockReturnValueOnce({
        isOpen: false,
        open: jest.fn(),
        close: jest.fn(),
      } as never)
      .mockReturnValueOnce({
        isOpen: false,
        open: jest.fn(),
        close: jest.fn(),
      } as never);

    mockedUseGlobalExplorer.mockReturnValue({
      item: {
        id: "folder-1",
        abilities: { children_create: true },
      },
      itemId: "folder-1",
    } as never);

    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: {
        getElementById: jest.fn(() => ({
          click: jest.fn(),
        })),
      },
    });
  });

  it("exposes import actions through the shared item import inputs when includeImport is enabled", () => {
    let capturedMenuItems:
      | ReturnType<typeof useCreateMenuItems>["menuItems"]
      | undefined;

    const Harness = () => {
      capturedMenuItems = useCreateMenuItems({ includeImport: true }).menuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const importFiles = capturedMenuItems?.find(
      (item) => "label" in item && item.label === "explorer.tree.import.files",
    );
    const importFolders = capturedMenuItems?.find(
      (item) => "label" in item && item.label === "explorer.tree.import.folders",
    );

    if (importFiles && "callback" in importFiles) {
      importFiles.callback?.();
    }
    if (importFolders && "callback" in importFolders) {
      importFolders.callback?.();
    }

    expect(document.getElementById).toHaveBeenCalledWith("import-files");
    expect(document.getElementById).toHaveBeenCalledWith("import-folders");
  });

  it("keeps the create folder entrypoint wired through the folder modal host", () => {
    const createFolderModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const createFileModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    let capturedMenuItems:
      | ReturnType<typeof useCreateMenuItems>["menuItems"]
      | undefined;

    mockedUseModal.mockReset();
    mockedUseModal
      .mockReturnValueOnce(createFolderModal as never)
      .mockReturnValueOnce(createFileModal as never);

    const Harness = () => {
      capturedMenuItems = useCreateMenuItems({ includeImport: true }).menuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const createFolder = capturedMenuItems?.find(
      (item) =>
        "label" in item &&
        item.label === "explorer.actions.createFolder.modal.title",
    );

    if (createFolder && "callback" in createFolder) {
      createFolder.callback?.();
    }

    expect(createFolderModal.open).toHaveBeenCalled();
  });

  it("keeps create folder before the shared import entries in the shell menu", () => {
    let capturedMenuItems:
      | ReturnType<typeof useCreateMenuItems>["menuItems"]
      | undefined;

    const Harness = () => {
      capturedMenuItems = useCreateMenuItems({ includeImport: true }).menuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const visibleLabels =
      capturedMenuItems?.flatMap((item) =>
        "label" in item && !item.isHidden ? [item.label] : [],
      ) ?? [];

    expect(visibleLabels.slice(0, 3)).toEqual([
      "explorer.actions.createFolder.modal.title",
      "explorer.tree.import.files",
      "explorer.tree.import.folders",
    ]);
  });
});
