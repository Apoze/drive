import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useRouter } from "next/router";
import { useAuth } from "@/features/auth/Auth";
import { useGlobalExplorer } from "../../GlobalExplorerContext";
import { useTreeContext } from "@gouvfr-lasuite/ui-kit";
import { ExplorerTree } from "../ExplorerTree";
import { getMountTreeNodeId } from "@/features/mounts/utils/mountTree";

const renderedTreeViewProps: Array<{
  selectedNodeId?: string;
  beforeMove?: (
    moveResult: {
      newParentId?: string;
      oldParentId?: string;
      sourceId: string;
    },
    moveCallback: () => void,
  ) => void;
}> = [];

const modalState = {
  isOpen: false,
  open: jest.fn(),
  close: jest.fn(),
};

const buildTreeNode = (overrides: Partial<Record<string, unknown>> = {}) =>
  ({
    id: "item-1",
    title: "Folder",
    path: "workspace-1.folder",
    abilities: {
      move: true,
    },
    ...overrides,
  }) as never;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  useModal: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  HorizontalSeparator: () => <div>separator</div>,
  IconSize: {
    SMALL: "small",
  },
  TreeView: (props: {
    selectedNodeId?: string;
    beforeMove?: (
      moveResult: {
        newParentId?: string;
        oldParentId?: string;
        sourceId: string;
      },
      moveCallback: () => void,
    ) => void;
  }) => {
    renderedTreeViewProps.push(props);
    return <div>tree-view</div>;
  },
  TreeViewNodeTypeEnum: {
    NODE: "node",
    SIMPLE_NODE: "simple-node",
  },
  useTreeContext: jest.fn(),
}));

jest.mock("../../GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("@/features/explorer/api/useMoveItem", () => ({
  useMoveItems: () => ({
    mutate: jest.fn(),
  }),
}));

jest.mock("@/features/explorer/components/ExplorerDndProvider", () => ({
  canDrop: jest.fn(() => true),
}));

jest.mock("../ExplorerTreeItem", () => ({
  ExplorerTreeItem: () => <div>tree-item</div>,
}));

jest.mock("../ExplorerTreeActions", () => ({
  ExplorerTreeActions: () => <div>tree-actions</div>,
}));

jest.mock("../nav/ExplorerTreeNav", () => ({
  ExplorerTreeNav: () => <div>tree-nav</div>,
}));

jest.mock("../nav/ExplorerTreeNavItem", () => ({
  ExplorerTreeNavItem: () => <div>tree-nav-item</div>,
}));

jest.mock("@/features/layouts/components/left-panel/LeftPanelMobile", () => ({
  LeftPanelMobile: () => <div>left-panel-mobile</div>,
}));

jest.mock("../ExplorerTreeMoveConfirmationModal", () => ({
  ExplorerTreeMoveConfirmationModal: () => <div>move-confirmation-modal</div>,
}));

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: jest.fn(),
  }),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: () => ({
    moveMountEntry: jest.fn(),
  }),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/features/explorer/components/toasts/addItemsMovedToast", () => ({
  addItemsMovedToast: jest.fn(),
}));

const mockedUseModal = jest.mocked(useModal);
const mockedUseRouter = jest.mocked(useRouter);
const mockedUseAuth = jest.mocked(useAuth);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedUseTreeContext = jest.mocked(useTreeContext);

describe("ExplorerTree", () => {
  const realUseState = React.useState;
  let useStateSpy: jest.SpiedFunction<typeof React.useState> | undefined;

  beforeEach(() => {
    renderedTreeViewProps.length = 0;
    modalState.isOpen = false;
    modalState.open.mockReset();
    modalState.close.mockReset();
    mockedUseModal.mockReturnValue(modalState as never);
    mockedUseRouter.mockReturnValue({
      pathname: "/explorer/items/my-files",
      query: {},
    } as never);
    mockedUseAuth.mockReturnValue({
      user: {
        id: "user-1",
      },
    } as never);
    mockedUseGlobalExplorer.mockReturnValue({
      itemId: "item-1",
      treeIsInitialized: true,
    } as never);
    mockedUseTreeContext.mockReturnValue({
      treeData: {
        nodes: [],
        getNode: jest.fn(),
        deleteNode: jest.fn(),
        addChild: jest.fn(),
      },
    } as never);
    let callCount = 0;
    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementation(((initialState?: unknown) => {
        callCount += 1;
        if (callCount === 2) {
          return [{ root: true }, jest.fn()] as never;
        }
        return realUseState(initialState as never);
      }) as typeof React.useState);
  });

  afterEach(() => {
    useStateSpy?.mockRestore();
  });

  it("passes the mount-aware selected node id to the canonical tree host", () => {
    mockedUseRouter.mockReturnValue({
      pathname: "/explorer/mounts/[mount_id]",
      query: {
        mount_id: "mount-1",
        path: "/folder",
      },
    } as never);

    const html = renderToStaticMarkup(<ExplorerTree />);

    expect(renderedTreeViewProps[0]?.selectedNodeId).toBe(
      getMountTreeNodeId("mount-1", "/folder"),
    );
    expect(html).toContain("tree-actions");
    expect(html).toContain("left-panel-mobile");
  });

  it("keeps same-workspace moves on the direct path without opening the confirmation modal", () => {
    const moveCallback = jest.fn();
    mockedUseTreeContext.mockReturnValue({
      treeData: {
        nodes: [],
        getNode: jest.fn((id: string) => {
          if (id === "source-1") {
            return buildTreeNode({
              id: "source-1",
              path: "workspace-1.folder.file",
            });
          }
          if (id === "old-parent") {
            return buildTreeNode({
              id: "old-parent",
              title: "Old parent",
              path: "workspace-1.folder-a",
            });
          }
          if (id === "new-parent") {
            return buildTreeNode({
              id: "new-parent",
              title: "New parent",
              path: "workspace-1.folder-b",
            });
          }
          return undefined;
        }),
        deleteNode: jest.fn(),
        addChild: jest.fn(),
      },
    } as never);

    renderToStaticMarkup(<ExplorerTree />);

    renderedTreeViewProps[0]?.beforeMove?.(
      {
        sourceId: "source-1",
        oldParentId: "old-parent",
        newParentId: "new-parent",
      },
      moveCallback,
    );

    expect(moveCallback).toHaveBeenCalledTimes(1);
    expect(modalState.open).not.toHaveBeenCalled();
  });

  it("opens the confirmation modal for cross-workspace moves", () => {
    mockedUseTreeContext.mockReturnValue({
      treeData: {
        nodes: [],
        getNode: jest.fn((id: string) => {
          if (id === "source-1") {
            return buildTreeNode({
              id: "source-1",
              path: "workspace-1.folder.file",
            });
          }
          if (id === "old-parent") {
            return buildTreeNode({
              id: "old-parent",
              title: "Workspace one",
              path: "workspace-1.folder-a",
            });
          }
          if (id === "new-parent") {
            return buildTreeNode({
              id: "new-parent",
              title: "Workspace two",
              path: "workspace-2.folder-b",
            });
          }
          return undefined;
        }),
        deleteNode: jest.fn(),
        addChild: jest.fn(),
      },
    } as never);

    renderToStaticMarkup(<ExplorerTree />);

    renderedTreeViewProps[0]?.beforeMove?.(
      {
        sourceId: "source-1",
        oldParentId: "old-parent",
        newParentId: "new-parent",
      },
      jest.fn(),
    );

    expect(modalState.open).toHaveBeenCalledTimes(1);
  });
});
