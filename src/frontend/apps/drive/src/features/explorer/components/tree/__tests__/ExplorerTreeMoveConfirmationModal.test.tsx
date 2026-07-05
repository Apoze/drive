import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ExplorerTreeMoveConfirmationModal } from "../ExplorerTreeMoveConfirmationModal";

const buttonProps: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
}> = [];

jest.mock("react-i18next", () => ({
  Trans: ({
    i18nKey,
    values,
  }: {
    i18nKey: string;
    values?: Record<string, unknown>;
  }) => <span>{`${i18nKey}:${JSON.stringify(values ?? {})}`}</span>,
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { children?: React.ReactNode; onClick?: () => void }) => {
    buttonProps.push(props);
    return <button>{props.children}</button>;
  },
  Modal: ({
    children,
    rightActions,
    title,
  }: {
    children?: React.ReactNode;
    rightActions?: React.ReactNode;
    title?: React.ReactNode;
  }) => (
    <div>
      {title}
      {rightActions}
      {children}
    </div>
  ),
  ModalSize: {
    MEDIUM: "medium",
  },
}));

describe("ExplorerTreeMoveConfirmationModal", () => {
  beforeEach(() => {
    buttonProps.length = 0;
  });

  it("keeps the standard inter-workspace confirmation copy and actions", () => {
    const onClose = jest.fn();
    const onMove = jest.fn();
    const html = renderToStaticMarkup(
      <ExplorerTreeMoveConfirmationModal
        isOpen={true}
        onClose={onClose}
        onMove={onMove}
        sourceItem={
          {
            id: "workspace-1",
            title: "Workspace one",
          } as never
        }
        targetItem={
          {
            id: "workspace-2",
            title: "Workspace two",
          } as never
        }
      />,
    );

    buttonProps[0]?.onClick?.();
    buttonProps[1]?.onClick?.();

    expect(html).toContain(
      "explorer.tree.workspace.move.confirmation_modal.description",
    );
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onMove).toHaveBeenCalledTimes(1);
  });

  it("keeps the dedicated root description when moving to a workspace root", () => {
    const html = renderToStaticMarkup(
      <ExplorerTreeMoveConfirmationModal
        isOpen={true}
        onClose={jest.fn()}
        onMove={jest.fn()}
        isMoveToRoot={true}
        sourceItem={
          {
            id: "workspace-1",
            title: "Workspace one",
          } as never
        }
        targetItem={
          {
            id: "workspace-2",
            title: "Workspace two",
          } as never
        }
      />,
    );

    expect(html).toContain(
      "explorer.tree.workspace.move.confirmation_modal.root_description",
    );
  });
});
