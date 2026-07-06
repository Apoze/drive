import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  useModal,
  useModals,
} from "@gouvfr-lasuite/cunningham-react";
import {
  useMutationHardDeleteItems,
  useMutationRestoreItems,
} from "@/features/explorer/hooks/useMutations";
import { BatchOperationError } from "@/features/errors/BatchOperationError";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { TrashBrowseExplorer } from "@/features/explorer/components/trash/TrashBrowseExplorer";

import TrashPage, {
  TrashPageSelectionBarActions,
} from "@/pages/explorer/trash";

const renderedButtonProps: Array<{
  onClick?: () => void;
  ariaLabel?: string;
}> = [];
const renderedHardDeleteModalProps: Array<{
  onDecide?: (decision: "yes" | null) => Promise<void> | void;
  count?: number;
}> = [];

const modalState = {
  isOpen: false,
  open: jest.fn(),
  close: jest.fn(),
};

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    onClick?: () => void;
    children?: React.ReactNode;
    ariaLabel?: string;
  }) => {
    renderedButtonProps.push(props);
    return <button>{props.children}</button>;
  },
  ModalSize: {
    MEDIUM: "medium",
  },
  useModal: jest.fn(),
  useModals: jest.fn(),
  VariantType: {
    INFO: "info",
  },
}));

jest.mock("@/features/explorer/hooks/useMutations", () => ({
  useMutationRestoreItems: jest.fn(),
  useMutationHardDeleteItems: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/features/explorer/components/GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("@/hooks/useDefaultRoute", () => ({
  useDefaultRoute: jest.fn(),
}));

jest.mock("@/features/explorer/components/trash/TrashBrowseExplorer", () => ({
  TrashBrowseExplorer: jest.fn(() => <div>trash-browse-explorer</div>),
}));

jest.mock(
  "@/features/explorer/components/modals/HardDeleteConfirmationModal",
  () => ({
    HardDeleteConfirmationModal: (props: {
      onDecide?: (decision: "yes" | null) => Promise<void> | void;
      count?: number;
    }) => {
      renderedHardDeleteModalProps.push(props);
      return <div>hard-delete-modal</div>;
    },
  }),
);

jest.mock("@/features/layouts/components/explorer/ExplorerLayout", () => ({
  getGlobalExplorerLayout: jest.fn((page) => page),
}));

jest.mock("@/assets/icons/undo_blue.svg", () => ({
  __esModule: true,
  default: { src: "/undo.svg" },
}));

jest.mock("@/assets/icons/cancel_blue.svg", () => ({
  __esModule: true,
  default: { src: "/cancel.svg" },
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/features/i18n/initI18n", () => ({
  __esModule: true,
  default: {
    t: (key: string) => key,
  },
}));

const mockedUseModal = jest.mocked(useModal);
const mockedUseModals = jest.mocked(useModals);
const mockedUseMutationRestoreItems = jest.mocked(useMutationRestoreItems);
const mockedUseMutationHardDeleteItems = jest.mocked(useMutationHardDeleteItems);
const mockedAddToast = jest.mocked(addToast);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedUseDefaultRoute = jest.mocked(useDefaultRoute);
const mockedTrashBrowseExplorer = jest.mocked(TrashBrowseExplorer);

describe("TrashPage", () => {
  const mutateRestoreAsync = jest.fn();
  const mutateHardDeleteAsync = jest.fn();
  const clearSelection = jest.fn();
  const replaceSelection = jest.fn();
  const messageModal = jest.fn();

  beforeEach(() => {
    renderedButtonProps.length = 0;
    renderedHardDeleteModalProps.length = 0;
    modalState.isOpen = false;
    modalState.open.mockReset();
    modalState.close.mockReset();
    mutateRestoreAsync.mockReset();
    mutateHardDeleteAsync.mockReset();
    clearSelection.mockReset();
    replaceSelection.mockReset();
    messageModal.mockReset();
    mockedAddToast.mockReset();
    mockedUseMutationRestoreItems.mockReturnValue({
      mutateAsync: mutateRestoreAsync,
    } as never);
    mockedUseMutationHardDeleteItems.mockReturnValue({
      mutateAsync: mutateHardDeleteAsync,
    } as never);
    mockedUseGlobalExplorer.mockReturnValue({
      selectedItems: [
        { id: "trash-1", title: "Trash one" },
        { id: "trash-2", title: "Trash two" },
      ],
      clearSelection,
      replaceSelection,
    } as never);
    mockedUseModal.mockImplementation(
      () =>
        ({
          isOpen: modalState.isOpen,
          open: () => {
            modalState.isOpen = true;
            modalState.open();
          },
          close: () => {
            modalState.isOpen = false;
            modalState.close();
          },
        }) as never,
    );
    mockedUseModals.mockReturnValue({
      messageModal,
    } as never);
  });

  it("wires the trash page host with header, default route and navigate modal", () => {
    renderToStaticMarkup(<TrashPage />);

    expect(mockedUseDefaultRoute).toHaveBeenCalledWith(DefaultRoute.TRASH);
    const props = mockedTrashBrowseExplorer.mock.calls[0][0] as {
      gridHeader: React.ReactNode;
      onNavigate: (event: unknown) => void;
      onFileClick: () => void;
    };
    const headerHtml = renderToStaticMarkup(props.gridHeader as React.ReactElement);

    expect(headerHtml).toContain("explorer.trash.title");
    expect(headerHtml).toContain("explorer.trash.description");

    props.onNavigate({} as never);

    expect(messageModal).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "explorer.trash.navigate.modal_folder.title",
      }),
    );

    props.onFileClick();

    expect(messageModal).toHaveBeenLastCalledWith(
      expect.objectContaining({
        title: "explorer.trash.navigate.modal_file.title",
      }),
    );
  });

  it("wires restore and hard delete actions from the selection bar", async () => {
    renderToStaticMarkup(<TrashPageSelectionBarActions />);

    await renderedButtonProps[0]?.onClick?.();

    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(mutateRestoreAsync).toHaveBeenCalledWith(["trash-1", "trash-2"]);
    expect(clearSelection).toHaveBeenCalledWith();

    renderedButtonProps[1]?.onClick?.();
    expect(modalState.open).toHaveBeenCalledTimes(1);
  });

  it("keeps only blocked trash items selected on partial restore failure", async () => {
    mutateRestoreAsync.mockRejectedValue(
      new BatchOperationError({
        completedIds: ["trash-1"],
        failedId: "trash-2",
        cause: new Error("403"),
      }),
    );

    renderToStaticMarkup(<TrashPageSelectionBarActions />);

    await renderedButtonProps[0]?.onClick?.();

    expect(clearSelection).not.toHaveBeenCalled();
    expect(replaceSelection).toHaveBeenCalledWith([
      { id: "trash-2", title: "Trash two" },
    ]);
    expect(mockedAddToast).toHaveBeenCalledTimes(2);
  });

  it("runs hard delete only on positive confirmation and passes the true selection count", async () => {
    modalState.isOpen = true;

    renderToStaticMarkup(<TrashPageSelectionBarActions />);

    expect(renderedHardDeleteModalProps[0]?.count).toBe(2);

    await renderedHardDeleteModalProps[0]?.onDecide?.(null);
    expect(mutateHardDeleteAsync).not.toHaveBeenCalled();

    await renderedHardDeleteModalProps[0]?.onDecide?.("yes");
    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(mutateHardDeleteAsync).toHaveBeenCalledWith(["trash-1", "trash-2"]);
    expect(clearSelection).toHaveBeenCalledWith();
  });

  it("passes counts above two to the hard delete modal without degrading them", () => {
    modalState.isOpen = true;
    mockedUseGlobalExplorer.mockReturnValue({
      selectedItems: [
        { id: "trash-1", title: "Trash one" },
        { id: "trash-2", title: "Trash two" },
        { id: "trash-3", title: "Trash three" },
      ],
      clearSelection,
      replaceSelection,
    } as never);

    renderToStaticMarkup(<TrashPageSelectionBarActions />);

    expect(renderedHardDeleteModalProps[0]?.count).toBe(3);
  });
});
