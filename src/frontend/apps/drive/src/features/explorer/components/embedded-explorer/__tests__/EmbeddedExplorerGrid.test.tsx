import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, ItemUploadState } from "@/features/drivers/types";
import { useItemActionMenuItems } from "../../../hooks/useItemActionMenuItems";
import { useDuplicatingItemsPoller } from "../../../hooks/useDuplicatingItemsPoller";
import { useOptionalDragItemContext } from "../../ExplorerDndProvider";
import { useTableKeyboardNavigation } from "../../../hooks/useTableKeyboardNavigation";
import { isTablet } from "@/features/ui/components/responsive/ResponsiveDivs";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useContextMenuContext } from "@gouvfr-lasuite/ui-kit";
import { EmbeddedExplorerGrid } from "../EmbeddedExplorerGrid";

const renderedRows: Array<Record<string, unknown>> = [];
const renderedDroppables: Array<{
  disabled?: boolean;
  item?: { id: string };
  onOver?: (isOver: boolean, item: { id: string }) => void;
}> = [];
const renderedMoveModalProps: Array<{
  isOpen?: boolean;
  itemsToMove?: Array<{ id: string }>;
  initialFolderId?: string;
}> = [];
const capturedUseReactTableArgs: Array<{
  columns?: Array<{ id: string }>;
}> = [];

jest.mock("react", () => {
  const actual = jest.requireActual("react");

  return {
    ...actual,
    createElement: (
      type: unknown,
      props: Record<string, unknown>,
      ...children: unknown[]
    ) => {
      if (type === "tr" && props?.["data-id"]) {
        renderedRows.push(props);
      }
      return actual.createElement(type as never, props, ...children);
    },
  };
});

jest.mock("react/jsx-runtime", () => {
  const actual = jest.requireActual("react/jsx-runtime");
  const captureRow =
    (render: typeof actual.jsx) =>
    (type: unknown, props: Record<string, unknown>, key?: string) => {
      if (type === "tr" && props?.["data-id"]) {
        renderedRows.push(props);
      }
      return render(type as never, props, key);
    };

  return {
    ...actual,
    jsx: captureRow(actual.jsx),
    jsxs: captureRow(actual.jsxs),
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

jest.mock("@tanstack/react-table", () => ({
  createColumnHelper: () => ({
    display: ({ id, cell }: { id: string; cell: unknown }) => ({
      id,
      columnDef: { cell },
    }),
    accessor: (key: string, { cell }: { cell: unknown }) => ({
      id: key,
      columnDef: { cell },
    }),
  }),
  useReactTable: ({
    data,
    columns,
  }: {
    data: Array<{ id: string }>;
    columns: Array<{ id: string; columnDef: { cell: unknown } }>;
  }) => {
    capturedUseReactTableArgs.push({ columns });
    return {
      getRowModel: () => ({
        rows: data.map((item, rowIndex) => ({
          id: `row-${rowIndex}`,
          original: item,
          getVisibleCells: () =>
            columns.map((column) => ({
              id: `${item.id}-${column.id}`,
              column: { columnDef: column.columnDef },
              getContext: () => ({
                cell: { id: `${item.id}-${column.id}` },
                row: { id: `row-${rowIndex}`, original: item },
              }),
            })),
        })),
      }),
    };
  },
  getCoreRowModel: jest.fn(),
  flexRender: (renderer: unknown, context: unknown) =>
    typeof renderer === "function"
      ? (renderer as (ctx: unknown) => unknown)(context)
      : renderer,
}));

jest.mock(
  "clsx",
  () =>
    (...values: unknown[]) =>
      values
        .flatMap((value) => {
          if (!value) return [];
          if (typeof value === "string") return [value];
          if (typeof value === "object") {
            return Object.entries(value as Record<string, boolean>)
              .filter(([, enabled]) => enabled)
              .map(([key]) => key);
          }
          return [];
        })
        .join(" "),
);

jest.mock("@/features/ui/components/responsive/ResponsiveDivs", () => ({
  isTablet: jest.fn(),
}));

jest.mock("@/features/explorer/components/Droppable", () => ({
  Droppable: (props: {
    children?: React.ReactNode;
    disabled?: boolean;
    item?: { id: string };
    onOver?: (isOver: boolean, item: { id: string }) => void;
  }) => {
    renderedDroppables.push(props);
    return <div>{props.children}</div>;
  },
}));

jest.mock("@/features/explorer/components/ExplorerDndProvider", () => ({
  useOptionalDragItemContext: jest.fn(),
}));

jest.mock("@/features/explorer/components/GlobalExplorerContext", () => ({
  NavigationEventType: {
    ITEM: 0,
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({
    children,
    icon,
    ...props
  }: {
    children?: React.ReactNode;
    icon?: React.ReactNode;
  }) => (
    <button {...props}>
      {icon}
      {children}
    </button>
  ),
  Tooltip: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  useModal: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  IconSize: {
    SMALL: "small",
  },
  iconSizeMap: {
    small: 16,
  },
  useContextMenuContext: jest.fn(),
}));

jest.mock("../../../hooks/useItemActionMenuItems", () => ({
  useItemActionMenuItems: jest.fn(),
}));

jest.mock("../../../hooks/useDuplicatingItemsPoller", () => ({
  useDuplicatingItemsPoller: jest.fn(),
}));

jest.mock("../../../hooks/useTableKeyboardNavigation", () => ({
  useTableKeyboardNavigation: jest.fn(),
}));

jest.mock("../../moveItemsModalLauncher", () => ({
  MoveItemsModalLauncher: (props: {
    isOpen?: boolean;
    itemsToMove?: Array<{ id: string }>;
    initialFolderId?: string;
  }) => {
    renderedMoveModalProps.push(props);
    return <div>move-items-modal</div>;
  },
}));

jest.mock("../EmbeddedExplorerGridMobileCell", () => ({
  EmbeddedExplorerGridMobileCell: ({
    row,
  }: {
    row: { original: { id: string } };
  }) => <div>mobile-cell:{row.original.id}</div>,
}));

jest.mock("../EmbeddedExplorerGridNameCell", () => ({
  EmbeddedExplorerGridNameCell: ({
    row,
  }: {
    row: { original: { id: string } };
  }) => <div>name-cell:{row.original.id}</div>,
}));

jest.mock("../EmbeddedExplorerGridUpdatedAtCell", () => ({
  EmbeddedExplorerGridUpdatedAtCell: ({
    row,
  }: {
    row: { original: { id: string } };
  }) => <div>updated-cell:{row.original.id}</div>,
}));

jest.mock("../EmbeddedExplorerGridActionsCell", () => ({
  EmbeddedExplorerGridActionsCell: ({
    row,
  }: {
    row: { original: { id: string } };
  }) => <div>actions-cell:{row.original.id}</div>,
}));

const mockedUseItemActionMenuItems = jest.mocked(useItemActionMenuItems);
const mockedUseDuplicatingItemsPoller = jest.mocked(useDuplicatingItemsPoller);
const mockedUseOptionalDragItemContext = jest.mocked(
  useOptionalDragItemContext,
);
const mockedUseTableKeyboardNavigation = jest.mocked(
  useTableKeyboardNavigation,
);
const mockedIsTablet = jest.mocked(isTablet);
const mockedUseModal = jest.mocked(useModal);
const mockedUseContextMenuContext = jest.mocked(useContextMenuContext);

const buildItem = (overrides: Record<string, unknown> = {}) =>
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
    upload_state: "ready",
    updated_at: new Date("2026-03-23T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-23T00:00:00Z"),
    path: "/Report.txt",
    abilities: {
      children_create: false,
      move: true,
    },
    ...overrides,
  }) as never;

const getRenderedRow = (id: string) => {
  const row = renderedRows.find((renderedRow) => renderedRow["data-id"] === id);
  expect(row).toBeDefined();
  return row!;
};

describe("EmbeddedExplorerGrid", () => {
  const contextMenuOpen = jest.fn();

  beforeEach(() => {
    renderedRows.length = 0;
    renderedDroppables.length = 0;
    renderedMoveModalProps.length = 0;
    capturedUseReactTableArgs.length = 0;
    contextMenuOpen.mockReset();
    mockedUseItemActionMenuItems.mockReturnValue({
      getMenuItems: jest.fn(() => [{ label: "generated-menu" }]),
      modals: <div>item-action-modals</div>,
      isModalOpen: false,
    } as never);
    mockedUseDuplicatingItemsPoller.mockClear();
    mockedUseOptionalDragItemContext.mockReturnValue(undefined);
    mockedUseTableKeyboardNavigation.mockReturnValue({
      onKeyDown: jest.fn(),
    } as never);
    mockedIsTablet.mockReturnValue(false);
    mockedUseModal.mockReturnValue({
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    } as never);
    mockedUseContextMenuContext.mockReturnValue({
      open: contextMenuOpen,
    } as never);
  });

  it("keeps desktop columns, selection and context menu wiring on the canonical host", () => {
    const setSelectedItems = jest.fn();
    const clearRightPanelItem = jest.fn();
    const getContextMenuItems = jest.fn(() => [{ label: "custom-menu" }]);

    const html = renderToStaticMarkup(
      <EmbeddedExplorerGrid
        items={[
          buildItem({
            id: "folder-1",
            type: ItemType.FOLDER,
            title: "Folder",
            abilities: { children_create: true, move: true },
          }),
        ]}
        onNavigate={jest.fn()}
        selectedItems={[]}
        setSelectedItems={setSelectedItems}
        clearRightPanelItem={clearRightPanelItem}
        getContextMenuItems={getContextMenuItems}
      />,
    );

    expect(
      capturedUseReactTableArgs[0]?.columns?.map((column) => column.id),
    ).toEqual(["mobile", "title", "info-col-1", "info-col-2", "actions"]);
    expect(html).toContain("name-cell:folder-1");
    expect(html).toContain("updated-cell:folder-1");
    expect(html).toContain("actions-cell:folder-1");
    expect(renderedMoveModalProps[0]).toMatchObject({
      isOpen: false,
      itemsToMove: [],
    });
    expect(mockedUseDuplicatingItemsPoller).toHaveBeenCalledWith([
      expect.objectContaining({ id: "folder-1" }),
    ]);
    expect(renderedDroppables[0]?.disabled).toBe(false);

    (
      getRenderedRow("folder-1").onClick as
        ((event: Record<string, unknown>) => void) | undefined
    )?.({
      target: {
        closest: () => ({}),
      },
      detail: 1,
      shiftKey: false,
      metaKey: false,
      ctrlKey: false,
    });

    (
      getRenderedRow("folder-1").onContextMenu as
        ((event: Record<string, unknown>) => void) | undefined
    )?.({
      preventDefault: jest.fn(),
      stopPropagation: jest.fn(),
      clientX: 10,
      clientY: 20,
    });

    expect(setSelectedItems).toHaveBeenCalledWith([
      expect.objectContaining({ id: "folder-1" }),
    ]);
    expect(clearRightPanelItem).toHaveBeenCalledTimes(1);
    expect(contextMenuOpen).toHaveBeenCalledWith({
      position: { x: 10, y: 20 },
      items: [{ label: "custom-menu" }],
    });
  });

  it("still opens the item context menu when the row is already selected", () => {
    const getContextMenuItems = jest.fn(() => [{ label: "custom-menu" }]);

    renderToStaticMarkup(
      <EmbeddedExplorerGrid
        items={[
          buildItem({
            id: "folder-1",
            type: ItemType.FOLDER,
            title: "Folder",
            abilities: { children_create: true, move: true },
          }),
        ]}
        onNavigate={jest.fn()}
        selectedItems={[
          buildItem({
            id: "folder-1",
            type: ItemType.FOLDER,
            title: "Folder",
            abilities: { children_create: true, move: true },
          }),
        ]}
        setSelectedItems={jest.fn()}
        getContextMenuItems={getContextMenuItems}
      />,
    );

    (
      getRenderedRow("folder-1").onContextMenu as
        ((event: Record<string, unknown>) => void) | undefined
    )?.({
      preventDefault: jest.fn(),
      stopPropagation: jest.fn(),
      clientX: 30,
      clientY: 40,
    });

    expect(getContextMenuItems).toHaveBeenCalledWith(
      expect.objectContaining({ id: "folder-1" }),
    );
    expect(contextMenuOpen).toHaveBeenCalledWith({
      position: { x: 30, y: 40 },
      items: [{ label: "custom-menu" }],
    });
  });

  it("keeps compact/mobile behavior and double-click navigation/file opening intact", () => {
    const onNavigate = jest.fn();
    const onFileClick = jest.fn();
    mockedIsTablet.mockReturnValue(true);

    renderToStaticMarkup(
      <EmbeddedExplorerGrid
        items={[
          buildItem({
            id: "folder-1",
            type: ItemType.FOLDER,
            title: "Folder",
            abilities: { children_create: true, move: true },
          }),
          buildItem({
            id: "file-1",
            type: ItemType.FILE,
            title: "File",
          }),
        ]}
        onNavigate={onNavigate}
        onFileClick={onFileClick}
        isCompact={true}
      />,
    );

    expect(
      capturedUseReactTableArgs[0]?.columns?.map((column) => column.id),
    ).toEqual(["mobile", "title"]);

    (
      getRenderedRow("folder-1").onClick as
        ((event: Record<string, unknown>) => void) | undefined
    )?.({
      target: {
        closest: () => ({}),
      },
      detail: 1,
    });
    (
      getRenderedRow("file-1").onClick as
        ((event: Record<string, unknown>) => void) | undefined
    )?.({
      target: {
        closest: () => ({}),
      },
      detail: 1,
    });

    expect(onNavigate).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 0,
        item: expect.objectContaining({ id: "folder-1" }),
      }),
    );
    expect(onFileClick).toHaveBeenCalledWith(
      expect.objectContaining({ id: "file-1" }),
    );
  });

  it("keeps local over-state wiring when no shared DnD context is present", () => {
    renderToStaticMarkup(
      <EmbeddedExplorerGrid
        items={[
          buildItem({
            id: "folder-1",
            type: ItemType.FOLDER,
            title: "Folder",
            abilities: { children_create: true, move: true },
          }),
        ]}
        onNavigate={jest.fn()}
      />,
    );

    renderedDroppables[0]?.onOver?.(true, { id: "other-item" });

    expect(renderedDroppables[0]?.item).toMatchObject({ id: "folder-1" });
  });

  it("disables row interactions and droppable targets while an item duplicates", () => {
    const setSelectedItems = jest.fn();
    const clearRightPanelItem = jest.fn();
    const getContextMenuItems = jest.fn(() => [{ label: "custom-menu" }]);

    renderToStaticMarkup(
      <EmbeddedExplorerGrid
        items={[
          buildItem({
            id: "file-copy",
            upload_state: ItemUploadState.DUPLICATING,
          }),
        ]}
        onNavigate={jest.fn()}
        onFileClick={jest.fn()}
        selectedItems={[]}
        setSelectedItems={setSelectedItems}
        clearRightPanelItem={clearRightPanelItem}
        getContextMenuItems={getContextMenuItems}
      />,
    );

    const row = getRenderedRow("file-copy");
    expect(row.className).toContain("duplicating");
    expect(row.className).not.toContain("selectable");

    (row.onClick as ((event: Record<string, unknown>) => void) | undefined)?.({
      target: {
        closest: () => ({}),
      },
      detail: 1,
      shiftKey: false,
      metaKey: false,
      ctrlKey: false,
    });

    (
      row.onContextMenu as
        ((event: Record<string, unknown>) => void) | undefined
    )?.({
      preventDefault: jest.fn(),
      stopPropagation: jest.fn(),
      clientX: 10,
      clientY: 20,
    });

    expect(setSelectedItems).not.toHaveBeenCalled();
    expect(clearRightPanelItem).not.toHaveBeenCalled();
    expect(getContextMenuItems).not.toHaveBeenCalled();
    expect(contextMenuOpen).not.toHaveBeenCalled();
    expect(renderedDroppables[0]?.disabled).toBe(true);
  });
});
