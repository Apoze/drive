import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, ItemUploadState, LinkReach } from "@/features/drivers/types";
import { useDisableDragGridItem } from "../hooks";
import { useEmbeddedExplorerGirdContext } from "../EmbeddedExplorerGrid";
import {
  EmbeddedExplorerGridNameCell,
  EmbeddedExplorerGridNameCellProps,
} from "../EmbeddedExplorerGridNameCell";
import {
  SelectionStore,
  SelectionStoreContext,
} from "../../../stores/selectionStore";

const renderedDraggables: Array<{
  disabled?: boolean;
  id?: string;
  item?: { id: string };
}> = [];
const renderedTooltips: Array<{
  content?: string;
}> = [];
const renderedIcons: Array<{
  name?: string;
}> = [];

jest.mock("@/features/explorer/components/Draggable", () => ({
  Draggable: (props: {
    children?: React.ReactNode;
    disabled?: boolean;
    id?: string;
    item?: { id: string };
  }) => {
    renderedDraggables.push(props);
    return <div>{props.children}</div>;
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Tooltip: (props: { children?: React.ReactNode; content?: string }) => {
    renderedTooltips.push(props);
    return <div>{props.children}</div>;
  },
}));

jest.mock("@/features/explorer/components/icons/ItemIcon", () => ({
  ItemIcon: ({ item }: { item: { id: string } }) => (
    <div>item-icon:{item.id}</div>
  ),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("../hooks", () => ({
  useDisableDragGridItem: jest.fn(),
}));

jest.mock("../EmbeddedExplorerGrid", () => ({
  useEmbeddedExplorerGirdContext: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: (props: { name?: string }) => {
    renderedIcons.push(props);
    return <div>{props.name}</div>;
  },
  Spinner: ({ size }: { size?: string }) => <div>spinner:{size}</div>,
  IconSize: {
    LARGE: "large",
    SMALL: "small",
  },
}));

const mockedUseDisableDragGridItem = jest.mocked(useDisableDragGridItem);
const mockedUseEmbeddedExplorerGirdContext = jest.mocked(
  useEmbeddedExplorerGirdContext,
);

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
    nb_accesses: 0,
    abilities: {
      move: true,
    },
    ...overrides,
  }) as never;

const renderWithSelectionStore = (
  children: React.ReactElement,
  selectedItems: Array<{ id: string }> = [],
) => {
  const selectionStore = new SelectionStore();
  selectionStore.setSelectedItems(selectedItems as never);
  return renderToStaticMarkup(
    <SelectionStoreContext.Provider value={selectionStore}>
      {children}
    </SelectionStoreContext.Provider>,
  );
};

describe("EmbeddedExplorerGridNameCell", () => {
  let useStateSpy: jest.SpiedFunction<typeof React.useState> | undefined;

  beforeEach(() => {
    renderedDraggables.length = 0;
    renderedTooltips.length = 0;
    renderedIcons.length = 0;
    mockedUseDisableDragGridItem.mockReturnValue(false);
    mockedUseEmbeddedExplorerGirdContext.mockReturnValue({
      disableItemDragAndDrop: false,
    } as never);
  });

  afterEach(() => {
    useStateSpy?.mockRestore();
  });

  it("keeps drag wrappers, tooltip overflow and public badge wiring intact", () => {
    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementationOnce((() => [true, jest.fn()]) as never);
    const params = {
      cell: { id: "cell-1" },
      row: {
        original: buildItem({
          computed_link_reach: LinkReach.PUBLIC,
        }),
      },
      children: <span>child</span>,
    } as unknown as EmbeddedExplorerGridNameCellProps;

    const html = renderWithSelectionStore(
      <EmbeddedExplorerGridNameCell {...params} />,
    );

    expect(html).toContain("item-icon:item-1");
    expect(html).toContain("Report");
    expect(html).toContain("child");
    expect(renderedTooltips[0]).toMatchObject({
      content: "Report",
    });
    expect(renderedDraggables[0]).toMatchObject({
      id: "cell-1",
      disabled: false,
      item: expect.objectContaining({ id: "item-1" }),
    });
    expect(renderedDraggables[1]).toMatchObject({
      id: "cell-1-title",
      disabled: false,
    });
    expect(renderedIcons[0]).toMatchObject({
      name: "public",
    });
  });

  it("keeps the inner title drag disabled when the row is already selected", () => {
    const params = {
      cell: { id: "cell-1" },
      row: {
        original: buildItem({
          nb_accesses: 2,
        }),
      },
    } as unknown as EmbeddedExplorerGridNameCellProps;

    renderWithSelectionStore(<EmbeddedExplorerGridNameCell {...params} />, [
      buildItem(),
    ]);

    expect(renderedDraggables[1]?.disabled).toBe(true);
    expect(renderedIcons[0]).toMatchObject({
      name: "people",
    });
  });

  it("shows the duplicating state and disables both drag handles", () => {
    const params = {
      cell: { id: "cell-1" },
      row: {
        original: buildItem({
          upload_state: ItemUploadState.DUPLICATING,
        }),
      },
    } as unknown as EmbeddedExplorerGridNameCellProps;

    const html = renderWithSelectionStore(
      <EmbeddedExplorerGridNameCell {...params} />,
    );

    expect(html).not.toContain("item-icon:item-1");
    expect(html).toContain("spinner:sm");
    expect(html).toContain("explorer.item.duplicating");
    expect(renderedDraggables[0]).toMatchObject({
      id: "cell-1",
      disabled: true,
    });
    expect(renderedDraggables[1]).toMatchObject({
      id: "cell-1-title",
      disabled: true,
    });
  });

  it("shows the converting state and disables both drag handles", () => {
    const params = {
      cell: { id: "cell-1" },
      row: {
        original: buildItem({
          upload_state: ItemUploadState.CONVERTING,
        }),
      },
    } as unknown as EmbeddedExplorerGridNameCellProps;

    const html = renderWithSelectionStore(
      <EmbeddedExplorerGridNameCell {...params} />,
    );

    expect(html).not.toContain("item-icon:item-1");
    expect(html).toContain("spinner:sm");
    expect(html).toContain("explorer.item.converting");
    expect(renderedDraggables[0]).toMatchObject({
      id: "cell-1",
      disabled: true,
    });
    expect(renderedDraggables[1]).toMatchObject({
      id: "cell-1-title",
      disabled: true,
    });
  });

  it("keeps analyzing items accessible", () => {
    const params = {
      cell: { id: "cell-1" },
      row: {
        original: buildItem({
          upload_state: ItemUploadState.ANALYZING,
        }),
      },
    } as unknown as EmbeddedExplorerGridNameCellProps;

    const html = renderWithSelectionStore(
      <EmbeddedExplorerGridNameCell {...params} />,
    );

    expect(html).toContain("item-icon:item-1");
    expect(html).not.toContain("spinner:sm");
    expect(renderedDraggables[0]).toMatchObject({
      id: "cell-1",
      disabled: false,
    });
    expect(renderedDraggables[1]).toMatchObject({
      id: "cell-1-title",
      disabled: false,
    });
  });
});
