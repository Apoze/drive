import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Item, ItemType } from "@/features/drivers/types";
import { timeAgo } from "@/features/explorer/utils/utils";
import { useDisableDragGridItem } from "../hooks";
import { EmbeddedExplorerGridUpdatedAtCell } from "../EmbeddedExplorerGridUpdatedAtCell";

const renderedDraggables: Array<{
  disabled?: boolean;
  id?: string;
  item?: { id: string };
}> = [];
const renderedTooltips: Array<{
  content?: string;
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

jest.mock("@/features/explorer/utils/utils", () => ({
  timeAgo: jest.fn(() => "1 day ago"),
}));

jest.mock("../hooks", () => ({
  useDisableDragGridItem: jest.fn(),
}));

const mockedTimeAgo = jest.mocked(timeAgo);
const mockedUseDisableDragGridItem = jest.mocked(useDisableDragGridItem);

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
      move: true,
    },
    ...overrides,
  }) as Item;

const buildCellContext = (
  item: Item = buildItem(),
): React.ComponentProps<typeof EmbeddedExplorerGridUpdatedAtCell> =>
  ({
    cell: { id: "cell-1" },
    row: {
      original: item,
    },
  }) as unknown as React.ComponentProps<typeof EmbeddedExplorerGridUpdatedAtCell>;

describe("EmbeddedExplorerGridUpdatedAtCell", () => {
  beforeEach(() => {
    renderedDraggables.length = 0;
    renderedTooltips.length = 0;
    mockedUseDisableDragGridItem.mockReturnValue(false);
  });

  it("keeps the draggable date cell and tooltip content intact", () => {
    const item = buildItem();
    const html = renderToStaticMarkup(
      <EmbeddedExplorerGridUpdatedAtCell {...buildCellContext(item)} />,
    );

    expect(html).toContain("1 day ago");
    expect(renderedDraggables[0]).toMatchObject({
      id: "cell-1",
      disabled: false,
      item: expect.objectContaining({ id: "item-1" }),
    });
    expect(renderedTooltips[0]).toMatchObject({
      content: item.updated_at.toLocaleString(),
    });
    expect(mockedTimeAgo).toHaveBeenCalledTimes(1);
  });
});
