import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import { useGlobalExplorer } from "../../components/GlobalExplorerContext";
import { useTableKeyboardNavigation } from "../useTableKeyboardNavigation";
import {
  SelectionStore,
  SelectionStoreContext,
} from "../../stores/selectionStore";

jest.mock("react", () => {
  const actual = jest.requireActual("react");
  return {
    ...actual,
    useEffect: (callback: () => void) => callback(),
  };
});

jest.mock("../../components/GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);

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

const buildTable = (items: Array<{ id: string }>) => ({
  getRowModel: () => ({
    rows: items.map((item) => ({ original: item })),
  }),
});

describe("useTableKeyboardNavigation", () => {
  let onKeyDown:
    | ((event: React.KeyboardEvent<HTMLTableElement>) => void)
    | undefined;

  const renderProbe = ({
    tableRef,
    isDisabled = false,
    items = [buildItem("item-1"), buildItem("item-2"), buildItem("item-3")],
    selectedItems = [],
  }: {
    tableRef: React.RefObject<HTMLTableElement | null>;
    isDisabled?: boolean;
    items?: Array<{ id: string }>;
    selectedItems?: Array<{ id: string }>;
  }) => {
    const selectionStore = new SelectionStore();
    selectionStore.setSelectedItems(selectedItems as never);

    const Probe = () => {
      const navigation = useTableKeyboardNavigation({
        table: buildTable(items) as never,
        tableRef,
        isDisabled,
      });
      onKeyDown = navigation.onKeyDown;
      return <div>probe</div>;
    };

    renderToStaticMarkup(
      <SelectionStoreContext.Provider value={selectionStore}>
        <Probe />
      </SelectionStoreContext.Provider>,
    );

    return selectionStore;
  };

  beforeEach(() => {
    onKeyDown = undefined;
    mockedUseGlobalExplorer.mockReturnValue({
      itemId: undefined,
    } as never);
  });

  it("focuses the table on render when keyboard navigation is enabled", () => {
    const focus = jest.fn();
    const tableRef = {
      current: {
        focus,
      },
    } as unknown as React.RefObject<HTMLTableElement | null>;

    renderProbe({ tableRef });

    expect(focus).toHaveBeenCalledWith({
      preventScroll: true,
    });
  });

  it("selects the first row on the first ArrowDown press when nothing is selected", () => {
    const selectionStore = renderProbe({
      tableRef: { current: null } as React.RefObject<HTMLTableElement | null>,
    });

    onKeyDown?.({ key: "ArrowDown" } as React.KeyboardEvent<HTMLTableElement>);

    expect(selectionStore.getSelectedItems()).toEqual([buildItem("item-1")]);
  });

  it("navigates down with shift by extending the current selection", () => {
    const item1 = buildItem("item-1");
    const item2 = buildItem("item-2");

    const selectionStore = renderProbe({
      tableRef: { current: null } as React.RefObject<HTMLTableElement | null>,
      items: [item1, item2],
      selectedItems: [item1],
    });

    onKeyDown?.({
      key: "ArrowDown",
      shiftKey: true,
    } as React.KeyboardEvent<HTMLTableElement>);

    expect(selectionStore.getSelectedItems().map((item) => item.id)).toEqual([
      "item-1",
      "item-2",
    ]);
  });

  it("navigates up by replacing the selection with the previous row", () => {
    const item1 = buildItem("item-1");
    const item2 = buildItem("item-2");

    const selectionStore = renderProbe({
      tableRef: { current: null } as React.RefObject<HTMLTableElement | null>,
      items: [item1, item2],
      selectedItems: [item2],
    });

    onKeyDown?.({ key: "ArrowUp" } as React.KeyboardEvent<HTMLTableElement>);

    expect(selectionStore.getSelectedItems()).toEqual([item1]);
  });

  it("resets the last selected index when itemId changes", () => {
    const setLastSelectedIndex = jest.fn();
    const useStateSpy = jest
      .spyOn(React, "useState")
      .mockReturnValue([2, setLastSelectedIndex] as never);

    mockedUseGlobalExplorer.mockReturnValue({
      itemId: "folder-2",
    } as never);

    renderProbe({
      tableRef: { current: null } as React.RefObject<HTMLTableElement | null>,
    });

    expect(setLastSelectedIndex).toHaveBeenCalledWith(null);

    useStateSpy.mockRestore();
  });

  it("does nothing when disabled", () => {
    const focus = jest.fn();

    const selectionStore = renderProbe({
      tableRef: {
        current: {
          focus,
        },
      } as unknown as React.RefObject<HTMLTableElement | null>,
      isDisabled: true,
    });

    onKeyDown?.({ key: "ArrowDown" } as React.KeyboardEvent<HTMLTableElement>);

    expect(focus).not.toHaveBeenCalled();
    expect(selectionStore.getSelectedItems()).toEqual([]);
  });
});
