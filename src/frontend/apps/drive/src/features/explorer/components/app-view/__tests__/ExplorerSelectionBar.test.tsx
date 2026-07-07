import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useGlobalExplorer } from "../../GlobalExplorerContext";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import { ExplorerSelectionBarActions } from "../ExplorerSelectionBar";
import { BatchDeleteError } from "@/features/errors/BatchDeleteError";
import {
  SelectionStore,
  SelectionStoreContext,
} from "@/features/explorer/stores/selectionStore";
import type { Item } from "@/features/drivers/types";

const mockDeleteMutateAsync = jest.fn();
const buttonProps: Array<{
  ["aria-label"]?: string;
  children?: React.ReactNode;
  onClick?: () => void | Promise<void>;
}> = [];
const renderedMoveModalProps: Array<{
  initialFolderId?: string;
  itemIds: string[];
}> = [];
const mockWindowAddEventListener = jest.fn();
const mockWindowRemoveEventListener = jest.fn();

jest.mock("react", () => {
  const actual = jest.requireActual("react");

  return {
    ...actual,
    useEffect: jest.fn((callback: () => void | (() => void)) => {
      callback();
    }),
  };
});

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => {
  const actual = jest.requireActual("@gouvfr-lasuite/cunningham-react");

  return {
    ...actual,
    Button: (props: {
      ["aria-label"]?: string;
      children?: React.ReactNode;
      onClick?: () => void | Promise<void>;
    }) => {
      buttonProps.push(props);
      return <button>{props.children}</button>;
    },
    useModal: jest.fn(),
  };
});

jest.mock("../../GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("@/features/explorer/components/app-view/AppExplorer", () => ({
  useAppExplorer: () => ({
    selectionBarActions: undefined,
  }),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({
    children,
    type,
  }: {
    children?: React.ReactNode;
    type?: string;
  }) => <div data-type={type ?? "default"}>{children}</div>,
}));

jest.mock("@/features/explorer/hooks/useMutations", () => ({
  useMutationDeleteItems: () => ({
    mutateAsync: mockDeleteMutateAsync,
  }),
}));

jest.mock("@/features/explorer/components/modals/move/ExplorerMoveFolderModal", () => ({
  ExplorerMoveFolder: ({
    initialFolderId,
    itemsToMove,
  }: {
    initialFolderId?: string;
    itemsToMove: Array<{ id: string }>;
  }) => {
    renderedMoveModalProps.push({
      initialFolderId,
      itemIds: itemsToMove.map((item) => item.id),
    });
    return <div>move-modal</div>;
  },
}));

jest.mock("@/features/explorer/components/modals/ExplorerZipItemsModal", () => ({
  ExplorerZipItemsModal: () => null,
}));

const mockedUseModal = jest.mocked(useModal);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedAddToast = jest.mocked(addToast);

const getToastMarkup = (index = 0) => {
  return renderToStaticMarkup(mockedAddToast.mock.calls[index][0] as React.ReactElement);
};

const renderWithSelectionStore = (
  element: React.ReactElement,
  selectedItems: Item[],
) => {
  const store = new SelectionStore();
  store.setSelectedItems(selectedItems);

  const html = renderToStaticMarkup(
    <SelectionStoreContext.Provider value={store}>
      {element}
    </SelectionStoreContext.Provider>,
  );

  return { html, store };
};

describe("ExplorerSelectionBarActions", () => {
  beforeEach(() => {
    buttonProps.length = 0;
    renderedMoveModalProps.length = 0;
    mockedAddToast.mockReset();
    mockDeleteMutateAsync.mockReset();
    mockDeleteMutateAsync.mockResolvedValue(undefined);
    mockWindowAddEventListener.mockReset();
    mockWindowRemoveEventListener.mockReset();
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: {
        addEventListener: mockWindowAddEventListener,
        removeEventListener: mockWindowRemoveEventListener,
      },
    });
  });

  it("opens the zip modal when the whole selection is readable", () => {
    const moveModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };
    const zipModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };

    mockedUseModal.mockReset();
    mockedUseModal.mockReturnValueOnce(moveModal as never);
    mockedUseModal.mockReturnValueOnce(zipModal as never);
    const selectedItems = [
      { id: "item-1", abilities: { retrieve: true } },
      { id: "item-2", abilities: { retrieve: true } },
    ] as Item[];
    mockedUseGlobalExplorer.mockReturnValue({
      clearSelection: jest.fn(),
      item: { id: "folder-1" },
      selectedItems,
    } as never);

    renderWithSelectionStore(<ExplorerSelectionBarActions />, selectedItems);

    const zipButton = buttonProps.find(
      (button) => button.children === "explorer.actions.archive.zip.button",
    );

    zipButton?.onClick?.();

    expect(zipModal.open).toHaveBeenCalled();
    expect(mockedAddToast).not.toHaveBeenCalled();
  });

  it("shows the zip low-rights toast instead of opening the modal", () => {
    const moveModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };
    const zipModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };

    mockedUseModal.mockReset();
    mockedUseModal.mockReturnValueOnce(moveModal as never);
    mockedUseModal.mockReturnValueOnce(zipModal as never);
    const selectedItems = [
      { id: "item-1", abilities: { retrieve: true } },
      { id: "item-2", abilities: { retrieve: false } },
    ] as Item[];
    mockedUseGlobalExplorer.mockReturnValue({
      clearSelection: jest.fn(),
      item: { id: "folder-1" },
      selectedItems,
    } as never);

    renderWithSelectionStore(<ExplorerSelectionBarActions />, selectedItems);

    const zipButton = buttonProps.find(
      (button) => button.children === "explorer.actions.archive.zip.button",
    );

    zipButton?.onClick?.();

    expect(zipModal.open).not.toHaveBeenCalled();
    expect(mockedAddToast).toHaveBeenCalledTimes(1);
  });

  it("opens the move modal with the selected items and current folder", () => {
    const moveModal = {
      close: jest.fn(),
      isOpen: true,
      open: jest.fn(),
    };
    const zipModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };

    mockedUseModal.mockReset();
    mockedUseModal.mockReturnValueOnce(moveModal as never);
    mockedUseModal.mockReturnValueOnce(zipModal as never);
    const selectedItems = [
      { id: "item-1", abilities: { retrieve: true } },
      { id: "item-2", abilities: { retrieve: true } },
    ] as Item[];
    mockedUseGlobalExplorer.mockReturnValue({
      clearSelection: jest.fn(),
      item: { id: "folder-1" },
      selectedItems,
    } as never);

    renderWithSelectionStore(<ExplorerSelectionBarActions />, selectedItems);

    const moveButton = buttonProps.find(
      (button) => button["aria-label"] === "explorer.selectionBar.move",
    );

    moveButton?.onClick?.();

    expect(moveModal.open).toHaveBeenCalled();
    expect(renderedMoveModalProps).toEqual([
      {
        initialFolderId: "folder-1",
        itemIds: ["item-1", "item-2"],
      },
    ]);
  });

  it("deletes the whole selection when every item is destroyable", async () => {
    const clearSelection = jest.fn();
    const replaceSelection = jest.fn();
    const closeRightPanelIfIncluded = jest.fn();
    const cancelUploadsForDeletedItems = jest.fn();
    const moveModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };
    const zipModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };

    mockedUseModal.mockReset();
    mockedUseModal.mockReturnValueOnce(moveModal as never);
    mockedUseModal.mockReturnValueOnce(zipModal as never);
    const selectedItems = [
      { id: "item-1", abilities: { destroy: true, retrieve: true } },
      { id: "item-2", abilities: { destroy: true, retrieve: true } },
    ] as Item[];
    mockedUseGlobalExplorer.mockReturnValue({
      clearSelection,
      replaceSelection,
      closeRightPanelIfIncluded,
      cancelUploadsForDeletedItems,
      item: { id: "folder-1" },
      selectedItems,
    } as never);

    const { store } = renderWithSelectionStore(
      <ExplorerSelectionBarActions />,
      selectedItems,
    );

    const deleteButton = buttonProps.find(
      (button) => button["aria-label"] === "explorer.selectionBar.delete",
    );

    await deleteButton?.onClick?.();

    expect(clearSelection).not.toHaveBeenCalled();
    expect(store.getSelectedItems()).toEqual([]);
    expect(cancelUploadsForDeletedItems).toHaveBeenCalledWith([
      "item-1",
      "item-2",
    ]);
    expect(closeRightPanelIfIncluded).toHaveBeenCalledWith(["item-1", "item-2"]);
    expect(replaceSelection).not.toHaveBeenCalled();
    expect(mockDeleteMutateAsync).toHaveBeenCalledWith(["item-1", "item-2"]);
    expect(getToastMarkup()).toContain("explorer.actions.delete.toast");
    expect(getToastMarkup()).toContain("data-type=\"default\"");
  });

  it("keeps only the failed item selected and shows a partial error toast after a partial delete", async () => {
    const clearSelection = jest.fn();
    const replaceSelection = jest.fn();
    const closeRightPanelIfIncluded = jest.fn();
    const cancelUploadsForDeletedItems = jest.fn();
    const moveModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };
    const zipModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };

    mockedUseModal.mockReset();
    mockedUseModal.mockReturnValueOnce(moveModal as never);
    mockedUseModal.mockReturnValueOnce(zipModal as never);
    const selectedItems = [
      {
        id: "item-1",
        title: "Folder A",
        abilities: { destroy: true, retrieve: true },
      },
      {
        id: "item-2",
        title: "Folder B",
        abilities: { destroy: true, retrieve: true },
      },
    ] as Item[];
    mockedUseGlobalExplorer.mockReturnValue({
      clearSelection,
      replaceSelection,
      closeRightPanelIfIncluded,
      cancelUploadsForDeletedItems,
      item: { id: "folder-1" },
      selectedItems,
    } as never);
    mockDeleteMutateAsync.mockRejectedValue(
      new BatchDeleteError({
        completedIds: ["item-1"],
        failedId: "item-2",
        cause: "forbidden",
      }),
    );

    renderWithSelectionStore(<ExplorerSelectionBarActions />, selectedItems);

    const deleteButton = buttonProps.find(
      (button) => button["aria-label"] === "explorer.selectionBar.delete",
    );

    await deleteButton?.onClick?.();

    expect(clearSelection).not.toHaveBeenCalled();
    expect(cancelUploadsForDeletedItems).toHaveBeenCalledWith(["item-1"]);
    expect(closeRightPanelIfIncluded).toHaveBeenCalledWith(["item-1"]);
    expect(replaceSelection).toHaveBeenCalledWith([
      {
        id: "item-2",
        title: "Folder B",
        abilities: { destroy: true, retrieve: true },
      },
    ]);
    expect(mockedAddToast).toHaveBeenCalledTimes(2);
    expect(getToastMarkup(0)).toContain("explorer.actions.delete.toast");
    expect(getToastMarkup(1)).toContain("explorer.actions.delete.partial_error");
  });

  it("shows the delete low-rights toast when one item is not destroyable", async () => {
    const clearSelection = jest.fn();
    const moveModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };
    const zipModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };

    mockedUseModal.mockReset();
    mockedUseModal.mockReturnValueOnce(moveModal as never);
    mockedUseModal.mockReturnValueOnce(zipModal as never);
    const selectedItems = [
      { id: "item-1", abilities: { destroy: true, retrieve: true } },
      { id: "item-2", abilities: { destroy: false, retrieve: true } },
    ] as Item[];
    mockedUseGlobalExplorer.mockReturnValue({
      clearSelection,
      replaceSelection: jest.fn(),
      closeRightPanelIfIncluded: jest.fn(),
      item: { id: "folder-1" },
      selectedItems,
    } as never);

    renderWithSelectionStore(<ExplorerSelectionBarActions />, selectedItems);

    const deleteButton = buttonProps.find(
      (button) => button["aria-label"] === "explorer.selectionBar.delete",
    );

    await deleteButton?.onClick?.();

    expect(clearSelection).not.toHaveBeenCalled();
    expect(mockDeleteMutateAsync).not.toHaveBeenCalled();
    expect(getToastMarkup()).toContain("explorer.actions.delete.low_rights_toast");
    expect(getToastMarkup()).toContain("data-type=\"error\"");
  });

  it("binds the keyboard delete shortcut to the same delete command", async () => {
    const clearSelection = jest.fn();
    const closeRightPanelIfIncluded = jest.fn();
    const cancelUploadsForDeletedItems = jest.fn();
    const moveModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };
    const zipModal = {
      close: jest.fn(),
      isOpen: false,
      open: jest.fn(),
    };

    mockedUseModal.mockReset();
    mockedUseModal.mockReturnValueOnce(moveModal as never);
    mockedUseModal.mockReturnValueOnce(zipModal as never);
    const selectedItems = [
      { id: "item-1", abilities: { destroy: true, retrieve: true } },
    ] as Item[];
    mockedUseGlobalExplorer.mockReturnValue({
      clearSelection,
      replaceSelection: jest.fn(),
      closeRightPanelIfIncluded,
      cancelUploadsForDeletedItems,
      item: { id: "folder-1" },
      selectedItems,
    } as never);

    const { store } = renderWithSelectionStore(
      <ExplorerSelectionBarActions />,
      selectedItems,
    );

    const keydownHandler = mockWindowAddEventListener.mock.calls.find(
      ([eventName]) => eventName === "keydown",
    )?.[1] as ((event: {
      metaKey?: boolean;
      ctrlKey?: boolean;
      key: string;
      preventDefault: () => void;
    }) => void) | undefined;

    expect(keydownHandler).toBeDefined();

    const preventDefault = jest.fn();
    keydownHandler?.({
      metaKey: true,
      ctrlKey: false,
      key: "Backspace",
      preventDefault,
    });
    await Promise.resolve();

    expect(preventDefault).toHaveBeenCalled();
    expect(clearSelection).not.toHaveBeenCalled();
    expect(store.getSelectedItems()).toEqual([]);
    expect(cancelUploadsForDeletedItems).toHaveBeenCalledWith(["item-1"]);
    expect(closeRightPanelIfIncluded).toHaveBeenCalledWith(["item-1"]);
    expect(mockDeleteMutateAsync).toHaveBeenCalledWith(["item-1"]);
  });
});
