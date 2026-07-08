import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useEmbeddedExplorer } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorer";
import { ArchiveExtractionModal } from "../ArchiveExtractionModal";
import { SelectionStore } from "@/features/explorer/stores/selectionStore";

const buttonProps: Array<{
  children?: React.ReactNode;
  disabled?: boolean;
  onClick?: () => void;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@dnd-kit/core", () => ({
  DndContext: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    disabled?: boolean;
    onClick?: () => void;
  }) => {
    buttonProps.push(props);
    return <button>{props.children}</button>;
  },
  Modal: ({
    children,
    rightActions,
  }: {
    children?: React.ReactNode;
    rightActions?: React.ReactNode;
  }) => (
    <div>
      {rightActions}
      {children}
    </div>
  ),
  ModalSize: {
    MEDIUM: "medium",
  },
}));

jest.mock(
  "@/features/explorer/components/embedded-explorer/EmbeddedExplorer",
  () => ({
    EmbeddedExplorer: () => <div>embedded-explorer</div>,
    useEmbeddedExplorer: jest.fn(),
  }),
);

const mockedUseEmbeddedExplorer = jest.mocked(useEmbeddedExplorer);

describe("ArchiveExtractionModal", () => {
  beforeEach(() => {
    buttonProps.length = 0;
  });

  it("confirms with the selected folder target when one folder is selected", () => {
    const onConfirm = jest.fn();
    const selectionStore = new SelectionStore();
    selectionStore.setSelectedItems([{ id: "folder-selected" }] as never);

    mockedUseEmbeddedExplorer.mockReturnValue({
      currentItemId: "folder-current",
      selectionStore,
    } as never);

    renderToStaticMarkup(
      <ArchiveExtractionModal
        initialFolderId="folder-current"
        isOpen={true}
        onClose={jest.fn()}
        onConfirm={onConfirm}
      />,
    );

    const confirmButton = buttonProps.find(
      (button) => button.children === "archive_viewer.extract.confirm",
    );

    confirmButton?.onClick?.();

    expect(onConfirm).toHaveBeenCalledWith("folder-selected");
  });

  it("falls back to the current folder target when nothing is selected", () => {
    const onConfirm = jest.fn();

    mockedUseEmbeddedExplorer.mockReturnValue({
      currentItemId: "folder-current",
      selectionStore: new SelectionStore(),
    } as never);

    renderToStaticMarkup(
      <ArchiveExtractionModal
        initialFolderId="folder-current"
        isOpen={true}
        onClose={jest.fn()}
        onConfirm={onConfirm}
      />,
    );

    const confirmButton = buttonProps.find(
      (button) => button.children === "archive_viewer.extract.confirm",
    );

    confirmButton?.onClick?.();

    expect(onConfirm).toHaveBeenCalledWith("folder-current");
  });
});
