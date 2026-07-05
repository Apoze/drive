import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useGlobalExplorer } from "../GlobalExplorerContext";
import { ExplorerDndProvider } from "../ExplorerDndProvider";
import { handleFavoriteCommand } from "../itemActionCommands";

const renderedDndContextProps: Array<{
  onDragStart?: (event: { active: { data: { current?: { item?: unknown } } } }) => void;
  onDragEnd?: (event: {
    active: { data: { current?: { item?: unknown } } };
    over?: { data: { current?: { item?: unknown } } };
  }) => Promise<void>;
}> = [];

const modalState = {
  isOpen: false,
  open: jest.fn(),
  close: jest.fn(),
};

const mockCreateFavoriteItem = jest.fn();
const mockMoveItems = jest.fn();
const mockSelectSingleItem = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@dnd-kit/core", () => ({
  DndContext: (props: {
    children?: React.ReactNode;
    onDragStart?: (event: { active: { data: { current?: { item?: unknown } } } }) => void;
    onDragEnd?: (event: {
      active: { data: { current?: { item?: unknown } } };
      over?: { data: { current?: { item?: unknown } } };
    }) => Promise<void>;
  }) => {
    renderedDndContextProps.push(props);
    return <div>{props.children}</div>;
  },
  DragOverlay: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  KeyboardSensor: function KeyboardSensor() {},
  MouseSensor: function MouseSensor() {},
  TouchSensor: function TouchSensor() {},
  useSensor: () => ({}),
  useSensors: () => [],
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  useModal: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  useTreeContext: () => ({
    treeData: {
      addChild: jest.fn(),
      moveNode: jest.fn(),
      getNode: jest.fn(),
      deleteNode: jest.fn(),
    },
  }),
  TreeViewNodeTypeEnum: {
    NODE: "node",
  },
}));

jest.mock("../GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
  getOriginalIdFromTreeId: jest.requireActual("../explorerTreeData")
    .getOriginalIdFromTreeId,
}));

jest.mock("../tree/ExploreDragOverlay", () => ({
  ExplorerDragOverlay: () => <div>drag-overlay</div>,
}));

jest.mock("../tree/ExplorerTreeMoveConfirmationModal", () => ({
  ExplorerTreeMoveConfirmationModal: () => <div>move-confirmation-modal</div>,
}));

jest.mock("../toasts/addItemsMovedToast", () => ({
  addItemsMovedToast: jest.fn(),
}));

jest.mock("../itemActionCommands", () => ({
  handleFavoriteCommand: jest.fn(),
}));

jest.mock("@/features/explorer/api/useMoveItem", () => ({
  useMoveItems: () => ({
    mutateAsync: mockMoveItems,
  }),
}));

jest.mock("@/features/explorer/hooks/useMutations", () => ({
  useMutationCreateFavoriteItem: () => ({
    mutateAsync: mockCreateFavoriteItem,
  }),
}));

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: jest.fn(),
  }),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: () => ({
    moveMountEntry: jest.fn(),
  }),
}));

const mockedUseModal = jest.mocked(useModal);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedHandleFavoriteCommand = jest.mocked(handleFavoriteCommand);

const buildItem = (overrides: Record<string, unknown> = {}) =>
  ({
    id: "item-1",
    title: "Folder",
    path: "workspace-1.folder",
    abilities: {
      children_create: true,
      move: true,
    },
    ...overrides,
  }) as never;

describe("ExplorerDndProvider", () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, "document", {
      value: {
        body: {
          style: {
            cursor: "",
          },
        },
      } as unknown as Document,
      configurable: true,
      writable: true,
    });
    renderedDndContextProps.length = 0;
    modalState.isOpen = false;
    modalState.open.mockReset();
    modalState.close.mockReset();
    mockCreateFavoriteItem.mockReset();
    mockMoveItems.mockReset();
    mockSelectSingleItem.mockReset();
    mockedHandleFavoriteCommand.mockReset();
    mockedUseModal.mockReturnValue(modalState as never);
    mockedUseGlobalExplorer.mockReturnValue({
      itemId: "current-folder",
      selectedItems: [],
      closePreview: jest.fn(),
      clearRightPanelItem: jest.fn(),
      closeRightPanel: jest.fn(),
      clearSelection: jest.fn(),
      selectSingleItem: mockSelectSingleItem,
    } as never);
  });

  afterEach(() => {
    Reflect.deleteProperty(globalThis, "document");
  });

  it("selects the dragged item when starting a drag outside an existing selection", () => {
    renderToStaticMarkup(
      <ExplorerDndProvider>
        <div>child</div>
      </ExplorerDndProvider>,
    );

    renderedDndContextProps[0]?.onDragStart?.({
      active: {
        data: {
          current: {
            item: buildItem({
              id: "item-1",
            }),
          },
        },
      },
    });

    expect(mockSelectSingleItem).toHaveBeenCalledWith(
      expect.objectContaining({ id: "item-1" }),
    );
  });

  it("routes favorites drops through the canonical favorite command with original ids", async () => {
    renderToStaticMarkup(
      <ExplorerDndProvider>
        <div>child</div>
      </ExplorerDndProvider>,
    );

    await renderedDndContextProps[0]?.onDragEnd?.({
      active: {
        data: {
          current: {
            item: buildItem({
              id: "favorites::item-1",
            }),
          },
        },
      },
      over: {
        data: {
          current: {
            item: buildItem({
              id: "favorites",
              path: "favorites",
            }),
          },
        },
      },
    });

    expect(mockedHandleFavoriteCommand).toHaveBeenCalledWith(
      expect.objectContaining({
        createFavoriteItem: mockCreateFavoriteItem,
        effectiveItemId: "item-1",
        item: expect.objectContaining({
          id: "item-1",
        }),
      }),
    );
  });

  it("opens the confirmation modal for cross-workspace drops", async () => {
    renderToStaticMarkup(
      <ExplorerDndProvider>
        <div>child</div>
      </ExplorerDndProvider>,
    );

    await renderedDndContextProps[0]?.onDragEnd?.({
      active: {
        data: {
          current: {
            item: buildItem({
              id: "item-1",
              path: "workspace-1.folder.file",
            }),
          },
        },
      },
      over: {
        data: {
          current: {
            item: buildItem({
              id: "folder-2",
              path: "workspace-2.folder",
            }),
          },
        },
      },
    });

    expect(modalState.open).toHaveBeenCalledTimes(1);
    expect(mockMoveItems).not.toHaveBeenCalled();
  });
});
