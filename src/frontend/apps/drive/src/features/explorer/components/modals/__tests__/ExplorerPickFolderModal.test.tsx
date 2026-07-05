import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ExplorerPickFolderModal } from "../ExplorerPickFolderModal";
import { useEmbeddedExplorer } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorer";

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

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  HorizontalSeparator: () => <div>separator</div>,
  useResponsive: () => ({
    isDesktop: true,
  }),
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
    FULL: "full",
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

describe("ExplorerPickFolderModal", () => {
  beforeEach(() => {
    buttonProps.length = 0;
  });

  it("submits the selected folder target when one folder is selected", () => {
    const onClose = jest.fn();
    const onPick = jest.fn();

    mockedUseEmbeddedExplorer.mockReturnValue({
      currentItemId: "folder-current",
      selectedItems: [{ id: "folder-selected" }],
    } as never);

    renderToStaticMarkup(
      <ExplorerPickFolderModal isOpen={true} onClose={onClose} onPick={onPick} />,
    );

    const submitButton = buttonProps.find(
      (button) =>
        button.children === "explorer.actions.archive.pickFolder.submit",
    );

    submitButton?.onClick?.();

    expect(onPick).toHaveBeenCalledWith("folder-selected");
    expect(onClose).toHaveBeenCalled();
  });

  it("falls back to the current folder target when no folder is selected", () => {
    const onClose = jest.fn();
    const onPick = jest.fn();

    mockedUseEmbeddedExplorer.mockReturnValue({
      currentItemId: "folder-current",
      selectedItems: [],
    } as never);

    renderToStaticMarkup(
      <ExplorerPickFolderModal isOpen={true} onClose={onClose} onPick={onPick} />,
    );

    const submitButton = buttonProps.find(
      (button) =>
        button.children === "explorer.actions.archive.pickFolder.submit",
    );

    submitButton?.onClick?.();

    expect(onPick).toHaveBeenCalledWith("folder-current");
    expect(onClose).toHaveBeenCalled();
  });
});
