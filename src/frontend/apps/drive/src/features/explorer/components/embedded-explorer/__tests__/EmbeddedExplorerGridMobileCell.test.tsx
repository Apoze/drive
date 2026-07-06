import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Item, ItemType, ItemUploadState } from "@/features/drivers/types";
import { timeAgo } from "@/features/explorer/utils/utils";
import { EmbeddedExplorerGridMobileCell } from "../EmbeddedExplorerGridMobileCell";

jest.mock("@/features/explorer/components/icons/ItemIcon", () => ({
  ItemIcon: ({ item }: { item: { id: string } }) => (
    <div>item-icon:{item.id}</div>
  ),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Spinner: ({ size }: { size?: string }) => <div>spinner:{size}</div>,
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

jest.mock("@/features/explorer/utils/utils", () => ({
  timeAgo: jest.fn(() => "3 hours ago"),
}));

const mockedTimeAgo = jest.mocked(timeAgo);

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
    abilities: {},
    ...overrides,
  }) as Item;

const buildCellContext = (
  item: Item = buildItem(),
): React.ComponentProps<typeof EmbeddedExplorerGridMobileCell> =>
  ({
    row: {
      original: item,
    },
  }) as unknown as React.ComponentProps<typeof EmbeddedExplorerGridMobileCell>;

describe("EmbeddedExplorerGridMobileCell", () => {
  beforeEach(() => {
    mockedTimeAgo.mockClear();
  });

  it("keeps the mobile title and relative date surface intact", () => {
    const html = renderToStaticMarkup(
      <EmbeddedExplorerGridMobileCell {...buildCellContext()} />,
    );

    expect(html).toContain("item-icon:item-1");
    expect(html).toContain("Report");
    expect(html).toContain("3 hours ago");
    expect(mockedTimeAgo).toHaveBeenCalledTimes(1);
  });

  it("shows a spinner and duplicating label for duplicating items", () => {
    const html = renderToStaticMarkup(
      <EmbeddedExplorerGridMobileCell
        {...buildCellContext(
          buildItem({ upload_state: ItemUploadState.DUPLICATING }),
        )}
      />,
    );

    expect(html).not.toContain("item-icon:item-1");
    expect(html).toContain("spinner:sm");
    expect(html).toContain("explorer.item.duplicating");
    expect(mockedTimeAgo).not.toHaveBeenCalled();
  });
});
