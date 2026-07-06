import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import { useGlobalExplorer } from "../../GlobalExplorerContext";
import { useAppExplorer } from "../AppExplorer";
import { useCreateMenuItems } from "../../../hooks/useCreateMenuItems";
import { useResponsive } from "@gouvfr-lasuite/ui-kit";
import { AppExplorerInner } from "../AppExplorerInner";

const capturedSelectionAreaProps: Array<Record<string, unknown>> = [];
const capturedContextMenuOptions: Array<unknown> = [];

jest.mock("react", () => {
  const actual = jest.requireActual("react");
  return {
    ...actual,
    useEffect: (callback: () => void) => callback(),
  };
});

jest.mock("@viselect/react", () => ({
  SelectionArea: (props: {
    children?: React.ReactNode;
    onBeforeStart?: unknown;
    onStart?: unknown;
    onMove?: unknown;
  }) => {
    capturedSelectionAreaProps.push(props as Record<string, unknown>);
    return <div data-testid="selection-area">{props.children}</div>;
  },
}));

jest.mock("clsx", () => (...values: unknown[]) =>
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

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  ContextMenu: ({
    options,
    children,
  }: {
    options?: unknown;
    children?: React.ReactNode;
  }) => {
    capturedContextMenuOptions.push(options);
    return <div>context-menu:{children}</div>;
  },
  HorizontalSeparator: () => <div>separator</div>,
  useResponsive: jest.fn(),
}));

jest.mock("../../GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("../AppExplorer", () => ({
  useAppExplorer: jest.fn(),
}));

jest.mock("../../../hooks/useCreateMenuItems", () => ({
  useCreateMenuItems: jest.fn(),
}));

jest.mock("../AppExplorerBreadcrumbs", () => ({
  AppExplorerBreadcrumbs: () => <div>breadcrumbs</div>,
  ExplorerBreadcrumbsMobile: () => <div>mobile-breadcrumbs</div>,
}));

jest.mock("../ExplorerSelectionBar", () => ({
  ExplorerSelectionBar: () => <div>selection-bar</div>,
}));

jest.mock("../ExplorerFilters", () => ({
  ExplorerFilters: () => <div>filters</div>,
}));

jest.mock("../AppExplorerGrid", () => ({
  AppExplorerGrid: () => <div>grid</div>,
}));

const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedUseAppExplorer = jest.mocked(useAppExplorer);
const mockedUseCreateMenuItems = jest.mocked(useCreateMenuItems);
const mockedUseResponsive = jest.mocked(useResponsive);

const buildItem = (id: string) =>
  ({
    id,
    title: `Item ${id}`,
    filename: `Item-${id}.txt`,
    creator: {
      id: "owner-1",
      full_name: "Owner",
      short_name: "OW",
    },
    type: ItemType.FILE,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-31T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-31T00:00:00Z"),
    path: `root.${id}`,
    abilities: {
      accesses_manage: false,
      accesses_view: true,
      children_create: false,
      children_list: false,
      destroy: false,
      favorite: false,
      invite_owner: false,
      link_configuration: false,
      media_auth: false,
      move: false,
      link_select_options: {
        restricted: null,
        authenticated: null,
        public: null,
      },
      partial_update: true,
      restore: false,
      retrieve: true,
      tree: false,
      update: true,
      upload_ended: true,
    },
  }) as never;

const mockAppExplorer = (overrides: Record<string, unknown> = {}) => {
  mockedUseAppExplorer.mockReturnValue({
    childrenItems: [],
    disableAreaSelection: false,
    disableDefaultContextMenu: false,
    dropZone: undefined,
    gridHeader: undefined,
    preserveIdleTopBarSpace: false,
    showFilters: true,
    ...overrides,
  } as never);
};

const createTarget = ({
  classes = [],
  closestSelectors = [],
  dataId,
  selected = false,
}: {
  classes?: string[];
  closestSelectors?: string[];
  dataId?: string;
  selected?: boolean;
}) => ({
  closest: (selector: string) =>
    closestSelectors.includes(selector) ? { selector } : null,
  classList: {
    contains: (className: string) =>
      classes.includes(className) ||
      (className === "selected" && selected),
  },
  getAttribute: (attribute: string) =>
    attribute === "data-id" ? dataId ?? null : null,
});

describe("AppExplorerInner", () => {
  beforeEach(() => {
    capturedSelectionAreaProps.length = 0;
    capturedContextMenuOptions.length = 0;
    mockedUseResponsive.mockReturnValue({ isTablet: false } as never);
    mockAppExplorer();
    mockedUseCreateMenuItems.mockReturnValue({
      menuItems: [{ label: "create-folder" }],
      modals: <div>create-modals</div>,
    } as never);
    mockedUseGlobalExplorer.mockReturnValue({
      setSelectedItems: jest.fn(),
      clearSelection: jest.fn(),
      itemId: "folder-1",
      clearRightPanelItem: jest.fn(),
      rightPanelForcedItem: undefined,
      rightPanelOpen: false,
      displayMode: "app",
      selectedItems: [],
      dropZone: {
        getRootProps: (props: Record<string, unknown>) => props,
        isFocused: false,
        isDragAccept: false,
        isDragReject: false,
      },
    } as never);
  });

  it("clears selection on item change and wires selection-area callbacks for the canonical host", () => {
    const clearSelection = jest.fn();
    const clearRightPanelItem = jest.fn();
    const setSelectedItems = jest.fn();

    mockedUseGlobalExplorer.mockReturnValue({
      setSelectedItems,
      clearSelection,
      itemId: "folder-1",
      clearRightPanelItem,
      rightPanelForcedItem: undefined,
      rightPanelOpen: false,
      displayMode: "app",
      selectedItems: [buildItem("item-2")],
      dropZone: {
        getRootProps: (props: Record<string, unknown>) => props,
        isFocused: false,
        isDragAccept: false,
        isDragReject: false,
      },
    } as never);
    mockAppExplorer({
      childrenItems: [buildItem("item-1"), buildItem("item-2")],
    });

    renderToStaticMarkup(<AppExplorerInner />);

    expect(clearSelection).toHaveBeenCalledTimes(1);

    clearSelection.mockClear();

    const selection = { clearSelection: jest.fn() };
    const selectionArea = capturedSelectionAreaProps[0] as {
      onStart: (params: {
        event?: { target?: HTMLElement; ctrlKey?: boolean; metaKey?: boolean };
        selection: typeof selection;
      }) => void;
      onBeforeStart: (params: {
        event?: { target?: HTMLElement; ctrlKey?: boolean; metaKey?: boolean };
        selection: typeof selection;
      }) => boolean | void;
      onMove: (params: {
        store: { changed: { added: HTMLElement[]; removed: HTMLElement[] } };
      }) => void;
    };

    selectionArea.onStart({
      event: { target: createTarget({}) as never, ctrlKey: false, metaKey: false },
      selection,
    });
    expect(selection.clearSelection).toHaveBeenCalledTimes(1);
    expect(clearSelection).toHaveBeenCalledTimes(1);

    selectionArea.onBeforeStart({
      event: {
        target: createTarget({ classes: ["explorer__content"] }) as never,
        ctrlKey: false,
        metaKey: false,
      },
      selection,
    });
    expect(selection.clearSelection).toHaveBeenCalledTimes(2);
    expect(clearSelection).toHaveBeenCalledTimes(2);
    expect(clearRightPanelItem).toHaveBeenCalledTimes(1);

    selectionArea.onMove({
      store: {
        changed: {
          added: [createTarget({ dataId: "item-1" }) as never],
          removed: [createTarget({ dataId: "item-2" }) as never],
        },
      },
    });

    expect(clearRightPanelItem).toHaveBeenCalledTimes(2);
    const updater = setSelectedItems.mock.calls[0][0] as (
      previous: Array<{ id: string }>,
    ) => Array<{ id: string }>;
    expect(updater([buildItem("item-2")]).map((item) => item.id)).toEqual([
      "item-1",
    ]);
  });

  it("ignores modal and selected-name starts, and keeps the forced right panel during selection move", () => {
    const clearSelection = jest.fn();
    const clearRightPanelItem = jest.fn();

    mockedUseGlobalExplorer.mockReturnValue({
      setSelectedItems: jest.fn(),
      clearSelection,
      itemId: undefined,
      clearRightPanelItem,
      rightPanelForcedItem: buildItem("item-99"),
      rightPanelOpen: true,
      displayMode: "app",
      selectedItems: [],
      dropZone: {
        getRootProps: (props: Record<string, unknown>) => props,
        isFocused: false,
        isDragAccept: false,
        isDragReject: false,
      },
    } as never);
    mockAppExplorer({
      childrenItems: [buildItem("item-1")],
    });

    renderToStaticMarkup(<AppExplorerInner />);

    const selectionArea = capturedSelectionAreaProps[0] as {
      onStart: (params: {
        event?: { target?: HTMLElement; ctrlKey?: boolean; metaKey?: boolean };
        selection: { clearSelection: jest.Mock };
      }) => void;
      onBeforeStart: (params: {
        event?: { target?: HTMLElement; ctrlKey?: boolean; metaKey?: boolean };
        selection: { clearSelection: jest.Mock };
      }) => boolean | void;
      onMove: (params: {
        store: { changed: { added: HTMLElement[]; removed: HTMLElement[] } };
      }) => void;
    };

    const selection = { clearSelection: jest.fn() };

    selectionArea.onStart({
      event: {
        target: createTarget({
          closestSelectors: ['[role="dialog"], .ReactModal__Overlay, .ReactModal__Content'],
        }) as never,
      },
      selection,
    });
    expect(selection.clearSelection).not.toHaveBeenCalled();
    expect(clearSelection).not.toHaveBeenCalled();

    expect(
      selectionArea.onBeforeStart({
        event: {
          target: createTarget({
            closestSelectors: [".explorer__grid__item__name__text"],
          }) as never,
        },
        selection,
      }),
    ).toBe(false);

    selectionArea.onMove({
      store: {
        changed: {
          added: [createTarget({ dataId: "item-1" }) as never],
          removed: [],
        },
      },
    });

    expect(clearRightPanelItem).not.toHaveBeenCalled();
  });

  it("bypasses area selection on tablet or when disabled, and drops the default context menu when requested", () => {
    mockedUseResponsive.mockReturnValue({ isTablet: true } as never);
    mockAppExplorer({
      childrenItems: [buildItem("item-1")],
      disableAreaSelection: true,
      disableDefaultContextMenu: true,
    });

    const html = renderToStaticMarkup(<AppExplorerInner />);

    expect(capturedSelectionAreaProps).toHaveLength(0);
    expect(capturedContextMenuOptions).toHaveLength(0);
    expect(html).toContain("grid");
    expect(html).not.toContain("context-menu");
    expect(html).not.toContain("create-modals");
  });
});
