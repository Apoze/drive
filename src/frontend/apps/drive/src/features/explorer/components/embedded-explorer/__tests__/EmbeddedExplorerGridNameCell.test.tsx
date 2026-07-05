import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, LinkReach } from "@/features/drivers/types";
import { useDisableDragGridItem } from "../hooks";
import { useEmbeddedExplorerGirdContext } from "../EmbeddedExplorerGrid";
import {
  EmbeddedExplorerGridNameCell,
  EmbeddedExplorerGridNameCellProps,
} from "../EmbeddedExplorerGridNameCell";

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
  ItemIcon: ({ item }: { item: { id: string } }) => <div>item-icon:{item.id}</div>,
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

describe("EmbeddedExplorerGridNameCell", () => {
  let useStateSpy: jest.SpiedFunction<typeof React.useState> | undefined;

  beforeEach(() => {
    renderedDraggables.length = 0;
    renderedTooltips.length = 0;
    renderedIcons.length = 0;
    mockedUseDisableDragGridItem.mockReturnValue(false);
    mockedUseEmbeddedExplorerGirdContext.mockReturnValue({
      selectedItemsMap: {},
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

    const html = renderToStaticMarkup(<EmbeddedExplorerGridNameCell {...params} />);

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
    mockedUseEmbeddedExplorerGirdContext.mockReturnValue({
      selectedItemsMap: { "item-1": buildItem() },
      disableItemDragAndDrop: false,
    } as never);
    const params = {
      cell: { id: "cell-1" },
      row: {
        original: buildItem({
          nb_accesses: 2,
        }),
      },
    } as unknown as EmbeddedExplorerGridNameCellProps;

    renderToStaticMarkup(<EmbeddedExplorerGridNameCell {...params} />);

    expect(renderedDraggables[1]?.disabled).toBe(true);
    expect(renderedIcons[0]).toMatchObject({
      name: "people",
    });
  });
});
