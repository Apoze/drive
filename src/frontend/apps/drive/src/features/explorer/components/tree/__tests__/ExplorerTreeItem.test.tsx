import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ItemType,
  TreeItemData,
} from "@/features/drivers/types";
import { ExplorerTreeItem } from "../ExplorerTreeItem";
import { useGlobalExplorer } from "../../GlobalExplorerContext";

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

jest.mock("../../GlobalExplorerContext", () => ({
  NavigationEventType: {
    ITEM: "ITEM",
  },
  useGlobalExplorer: jest.fn(),
}));

jest.mock("../DroppableNodeTree", () => ({
  DroppableNodeTree: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

let capturedTreeItemOnClick: (() => void) | undefined;

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: () => <span>icon</span>,
  IconSize: {
    MEDIUM: "medium",
    SMALL: "small",
  },
  TreeViewItem: ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => {
    capturedTreeItemOnClick = onClick;
    return <div>{children}</div>;
  },
  TreeViewNodeTypeEnum: {
    NODE: "node",
    SIMPLE_NODE: "simple_node",
  },
}));

jest.mock("../../icons/ItemIcon", () => ({
  ItemIcon: () => <div>item-icon</div>,
}));

jest.mock("../ExplorerTreeItemActions", () => ({
  ExplorerTreeItemActions: () => <div>tree-item-actions</div>,
}));

jest.mock("../MountTreeItemActions", () => ({
  MountTreeItemActions: () => <div>mount-tree-item-actions</div>,
}));

jest.mock("@/features/ui/components/icon/MountsIcon", () => ({
  MountsIcon: () => <div>mounts-icon</div>,
}));

jest.mock("@/features/mounts/utils/mountTree", () => ({
  isMountTreeItem: () => false,
}));

const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);

describe("ExplorerTreeItem", () => {
  beforeEach(() => {
    capturedTreeItemOnClick = undefined;
    mockedUseGlobalExplorer.mockReturnValue({
      onNavigate: jest.fn(),
      openSinglePreview: jest.fn(),
    } as never);
  });

  it("opens file nodes through the explicit single-preview API", () => {
    const openSinglePreview = jest.fn();
    const fileItem = {
      id: "item-1",
      title: "Report",
      type: ItemType.FILE,
      nodeType: "node",
    } as unknown as TreeItemData;

    mockedUseGlobalExplorer.mockReturnValue({
      onNavigate: jest.fn(),
      openSinglePreview,
    } as never);
    const props = {
      node: {
        id: "item-1",
        data: {
          value: fileItem,
        },
      },
      style: {},
      tree: {},
    } as React.ComponentProps<typeof ExplorerTreeItem>;

    renderToStaticMarkup(
      <ExplorerTreeItem {...props} />,
    );

    capturedTreeItemOnClick?.();

    expect(openSinglePreview).toHaveBeenCalledWith(fileItem);
  });
});
