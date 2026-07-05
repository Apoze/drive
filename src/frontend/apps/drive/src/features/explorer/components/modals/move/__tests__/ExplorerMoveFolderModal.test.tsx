import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, ItemUploadState, LinkReach, LinkRole, Role } from "@/features/drivers/types";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useEmbeddedExplorer } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorer";
import { useMoveItems } from "@/features/explorer/api/useMoveItem";
import { useItem } from "@/features/explorer/hooks/useQueries";
import { useQueryClient } from "@tanstack/react-query";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import { ExplorerMoveFolder } from "../ExplorerMoveFolderModal";

const buttonProps: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
}> = [];

jest.mock("react-i18next", () => ({
  Trans: ({ i18nKey }: { i18nKey: string }) => <span>{i18nKey}</span>,
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  HorizontalSeparator: () => <div>separator</div>,
  useResponsive: () => ({
    isDesktop: true,
  }),
  useTreeContext: () => ({
    treeData: {
      getNode: jest.fn(() => ({
        children: [],
      })),
      moveNode: jest.fn(),
    },
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { children?: React.ReactNode; onClick?: () => void }) => {
    buttonProps.push(props);
    return <button>{props.children}</button>;
  },
  Modal: ({
    children,
    leftActions,
    rightActions,
  }: {
    children?: React.ReactNode;
    leftActions?: React.ReactNode;
    rightActions?: React.ReactNode;
  }) => (
    <div>
      {leftActions}
      {rightActions}
      {children}
    </div>
  ),
  ModalSize: {
    FULL: "full",
    MEDIUM: "medium",
  },
  useModal: jest.fn(),
}));

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: jest.fn(),
}));

jest.mock("@/features/explorer/api/useMoveItem", () => ({
  useMoveItems: jest.fn(),
}));

jest.mock("@/features/explorer/hooks/useQueries", () => ({
  useItem: jest.fn(),
}));

jest.mock("@/features/explorer/components/toasts/addItemsMovedToast", () => ({
  addItemsMovedToast: jest.fn(),
}));

jest.mock("@/features/explorer/components/GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock(
  "@/features/explorer/components/embedded-explorer/EmbeddedExplorer",
  () => ({
    EmbeddedExplorer: () => <div>embedded-explorer</div>,
    useEmbeddedExplorer: jest.fn(),
  }),
);

jest.mock(
  "@/features/explorer/components/tree/ExplorerTreeMoveConfirmationModal",
  () => ({
    ExplorerTreeMoveConfirmationModal: () => null,
  }),
);

jest.mock(
  "@/features/explorer/components/modals/ExplorerCreateFolderModal",
  () => ({
    ExplorerCreateFolderModal: () => null,
  }),
);

const mockedUseModal = jest.mocked(useModal);
const mockedUseEmbeddedExplorer = jest.mocked(useEmbeddedExplorer);
const mockedUseMoveItems = jest.mocked(useMoveItems);
const mockedUseItem = jest.mocked(useItem);
const mockedUseQueryClient = jest.mocked(useQueryClient);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);

const buildItemToMove = () =>
  ({
    id: "item-1",
    title: "Report",
    filename: "Report.txt",
    creator: {
      id: "user-1",
      full_name: "Jane Doe",
      short_name: "JD",
    },
    type: ItemType.FILE,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: ItemUploadState.READY,
    updated_at: new Date("2026-03-22T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-22T00:00:00Z"),
    path: "root.old-parent.item-1",
    mimetype: "text/plain",
    link_reach: LinkReach.RESTRICTED,
    link_role: LinkRole.READER,
    user_role: Role.OWNER,
    abilities: {
      accesses_manage: false,
      accesses_view: true,
      children_create: false,
      children_list: false,
      destroy: true,
      favorite: false,
      invite_owner: false,
      link_configuration: false,
      media_auth: false,
      move: true,
      link_select_options: {
        [LinkReach.RESTRICTED]: null,
        [LinkReach.AUTHENTICATED]: null,
        [LinkReach.PUBLIC]: null,
      },
      partial_update: false,
      restore: false,
      retrieve: true,
      tree: false,
      update: true,
      upload_ended: false,
    },
  }) as never;

describe("ExplorerMoveFolder", () => {
  beforeEach(() => {
    buttonProps.length = 0;
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
  });

  it("moves into the current folder target when no folder is selected", () => {
    const mutateAsync = jest.fn();
    const clearSelection = jest.fn();

    mockedUseGlobalExplorer.mockReturnValue({
      itemId: "current-item",
    } as never);
    mockedUseQueryClient.mockReturnValue({
      invalidateQueries: jest.fn(),
    } as never);
    mockedUseMoveItems.mockReturnValue({
      mutateAsync,
    } as never);
    mockedUseEmbeddedExplorer.mockReturnValue({
      clearSelection,
      currentItemId: "folder-destination",
      selectedItems: [],
    } as never);
    mockedUseItem.mockReturnValue({
      data: {
        id: "folder-destination",
        path: "root.folder-destination",
      },
    } as never);

    renderToStaticMarkup(
      <ExplorerMoveFolder
        isOpen={true}
        onClose={jest.fn()}
        itemsToMove={[buildItemToMove()]}
      />,
    );

    const moveButton = buttonProps.find(
      (button) => button.children === "explorer.modal.move.move_button",
    );

    moveButton?.onClick?.();

    expect(mutateAsync).toHaveBeenCalledWith(
      {
        ids: ["item-1"],
        oldParentId: "old-parent",
        parentId: "folder-destination",
      },
      expect.any(Object),
    );
  });
});
