import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useDndContext, useDroppable } from "@dnd-kit/core";
import { useTreeContext, TreeViewNodeTypeEnum } from "@gouvfr-lasuite/ui-kit";
import { DroppableNodeTree } from "../DroppableNodeTree";

jest.mock("@dnd-kit/core", () => ({
  useDndContext: jest.fn(),
  useDroppable: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  useTreeContext: jest.fn(),
  TreeViewNodeTypeEnum: {
    NODE: "node",
    SIMPLE_NODE: "simple-node",
  },
}));

jest.mock("@/features/explorer/components/ExplorerDndProvider", () => ({
  canDrop: jest.fn(() => true),
}));

const mockedUseDndContext = jest.mocked(useDndContext);
const mockedUseDroppable = jest.mocked(useDroppable);
const mockedUseTreeContext = jest.mocked(useTreeContext);

describe("DroppableNodeTree", () => {
  let useEffectSpy: jest.SpiedFunction<typeof React.useEffect> | undefined;

  beforeEach(() => {
    mockedUseDndContext.mockReturnValue({
      active: {
        data: {
          current: {
            item: {
              id: "item-1",
              path: "workspace.folder.file",
              abilities: {
                move: true,
              },
            },
          },
        },
      },
    } as never);
    mockedUseDroppable.mockReturnValue({
      isOver: false,
      setNodeRef: jest.fn(),
    } as never);
    mockedUseTreeContext.mockReturnValue({
      treeData: {
        handleLoadChildren: jest.fn(),
      },
    } as never);
    useEffectSpy = jest
      .spyOn(React, "useEffect")
      .mockImplementation(((effect: () => void | (() => void)) => {
        effect();
      }) as typeof React.useEffect);
  });

  afterEach(() => {
    useEffectSpy?.mockRestore();
    jest.useRealTimers();
  });

  it("keeps the non-droppable branch inert for simple tree nodes", () => {
    const html = renderToStaticMarkup(
      <DroppableNodeTree
        id="simple-node"
        item={
          {
            id: "simple-node",
            nodeType: TreeViewNodeTypeEnum.SIMPLE_NODE,
            path: "workspace.simple",
          } as never
        }
      >
        <span>child</span>
      </DroppableNodeTree>,
    );

    expect(html).toContain("explorer__tree__item__droppable");
    expect(html).toContain("child");
    expect(mockedUseDroppable).toHaveBeenCalledWith(
      expect.objectContaining({
        disabled: true,
      }),
    );
  });

  it("auto-opens and lazy-loads a hovered folder node after the canonical delay", async () => {
    jest.useFakeTimers();
    mockedUseDroppable.mockReturnValue({
      isOver: true,
      setNodeRef: jest.fn(),
    } as never);

    const handleLoadChildren = jest.fn().mockResolvedValue(undefined);
    const open = jest.fn();

    mockedUseTreeContext.mockReturnValue({
      treeData: {
        handleLoadChildren,
      },
    } as never);

    renderToStaticMarkup(
      <DroppableNodeTree
        id="folder-node"
        item={
          {
            id: "folder-node",
            nodeType: TreeViewNodeTypeEnum.NODE,
            path: "workspace.folder",
            abilities: {
              children_create: true,
            },
          } as never
        }
        nodeTree={
          {
            node: {
              data: {
                value: {
                  id: "folder-node",
                  children: [],
                  childrenCount: 1,
                },
              },
              open,
            },
          } as never
        }
      >
        <span>child</span>
      </DroppableNodeTree>,
    );

    jest.advanceTimersByTime(800);
    await Promise.resolve();

    expect(handleLoadChildren).toHaveBeenCalledWith("folder-node");
    expect(open).toHaveBeenCalledTimes(1);
  });
});
