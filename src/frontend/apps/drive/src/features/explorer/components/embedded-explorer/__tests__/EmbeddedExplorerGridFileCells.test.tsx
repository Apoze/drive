import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Item, ItemType, ItemUploadState } from "@/features/drivers/types";
import { formatSize } from "@/features/explorer/utils/utils";
import { useDisableDragGridItem } from "../hooks";
import { FileSizeCell } from "../cells/FileSizeCell";
import { FileTypeCell } from "../cells/FileTypeCell";

const renderedDraggables: Array<{
  disabled?: boolean;
  id?: string;
  item?: { id: string };
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

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => `translated:${key}`,
  }),
}));

jest.mock("@/features/explorer/utils/utils", () => {
  return {
    formatSize: jest.fn((_size: number, t: (key: string) => string) =>
      t("explorer.grid.size_units.KB"),
    ),
    getExtension: (item: { filename?: string }) => {
      const parts = item.filename?.split(".") ?? [];
      return parts.length > 1 ? parts[parts.length - 1] : null;
    },
  };
});

jest.mock("../hooks", () => ({
  useDisableDragGridItem: jest.fn(),
}));

const mockedFormatSize = jest.mocked(formatSize);
const mockedUseDisableDragGridItem = jest.mocked(useDisableDragGridItem);

const buildItem = (overrides: Partial<Item> = {}): Item =>
  ({
    id: "item-1",
    title: "Report",
    filename: "Report.final.pdf",
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
    upload_state: ItemUploadState.READY,
    updated_at: new Date("2026-03-23T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-23T00:00:00Z"),
    path: "/Report.final.pdf",
    size: 1500,
    abilities: {
      move: true,
    },
    ...overrides,
  }) as Item;

const buildCellContext = (item: Item = buildItem()) =>
  ({
    cell: { id: "cell-1" },
    row: {
      original: item,
    },
  }) as unknown as React.ComponentProps<typeof FileSizeCell>;

describe("EmbeddedExplorerGrid file info cells", () => {
  beforeEach(() => {
    renderedDraggables.length = 0;
    mockedFormatSize.mockClear();
    mockedUseDisableDragGridItem.mockReturnValue(false);
  });

  it("renders localized file sizes and preserves draggable wiring", () => {
    const html = renderToStaticMarkup(
      <FileSizeCell {...buildCellContext()} />,
    );

    expect(html).toContain("translated:explorer.grid.size_units.KB");
    expect(mockedFormatSize).toHaveBeenCalledWith(1500, expect.any(Function));
    expect(renderedDraggables[0]).toMatchObject({
      id: "cell-1",
      disabled: false,
      item: expect.objectContaining({ id: "item-1" }),
    });
  });

  it("keeps folders and missing sizes as dash placeholders", () => {
    const folder = buildItem({
      type: ItemType.FOLDER,
      size: undefined,
    });

    const html = renderToStaticMarkup(
      <FileSizeCell {...buildCellContext(folder)} />,
    );

    expect(html).toContain("-");
    expect(mockedFormatSize).not.toHaveBeenCalled();
  });

  it("renders file extensions in the file type cell", () => {
    const html = renderToStaticMarkup(
      <FileTypeCell {...buildCellContext()} />,
    );

    expect(html).toContain(".pdf");
  });

  it("keeps folders and extensionless files on safe fallback labels", () => {
    const folderHtml = renderToStaticMarkup(
      <FileTypeCell {...buildCellContext(buildItem({ type: ItemType.FOLDER }))} />,
    );
    const fileHtml = renderToStaticMarkup(
      <FileTypeCell {...buildCellContext(buildItem({ filename: "README" }))} />,
    );

    expect(folderHtml).toContain("translated:explorer.grid.columns.folder");
    expect(fileHtml).toContain("-");
  });
});
