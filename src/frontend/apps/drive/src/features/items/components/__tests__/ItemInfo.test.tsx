import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemInfo } from "../ItemInfo";
import { Item, ItemType, ItemUploadState, LinkReach, LinkRole } from "@/features/drivers/types";
import { getFormatTranslationKey } from "@/features/explorer/utils/mimeTypes";
import { formatSize } from "@/features/explorer/utils/utils";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => `translated:${key}`,
  }),
}));

jest.mock("@/features/explorer/utils/mimeTypes", () => ({
  getFormatTranslationKey: jest.fn(),
}));

jest.mock("@/features/explorer/utils/utils", () => ({
  formatSize: jest.fn(),
}));

jest.mock("@/features/ui/components/info/InfoRow", () => ({
  InfoRow: ({
    label,
    rightContent,
  }: {
    label: React.ReactNode;
    rightContent?: React.ReactNode;
  }) => (
    <div data-testid="info-row">
      <span>{label}</span>
      <span>{rightContent}</span>
    </div>
  ),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  UserRow: ({ fullName }: { fullName: string }) => <span>{fullName}</span>,
}));

const mockedGetFormatTranslationKey = jest.mocked(getFormatTranslationKey);
const mockedFormatSize = jest.mocked(formatSize);

const buildItem = (overrides: Partial<Item> = {}): Item => ({
  id: "item-1",
  title: "Quarterly report",
  filename: "Quarterly report.pdf",
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
  updated_at: new Date("2026-03-30T12:00:00Z"),
  description: "",
  created_at: new Date("2026-03-29T08:30:00Z"),
  path: "/Quarterly report.pdf",
  size: 2048,
  mimetype: "application/pdf",
  link_reach: LinkReach.RESTRICTED,
  link_role: LinkRole.READER,
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
      [LinkReach.RESTRICTED]: null,
      [LinkReach.AUTHENTICATED]: null,
      [LinkReach.PUBLIC]: null,
    },
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: false,
    update: false,
    upload_ended: false,
  },
  ...overrides,
});

describe("ItemInfo", () => {
  let toLocaleStringSpy: jest.SpyInstance<string, [locales?: Intl.LocalesArgument, options?: Intl.DateTimeFormatOptions]>;

  beforeEach(() => {
    mockedGetFormatTranslationKey.mockReturnValue("mime.pdf");
    mockedFormatSize.mockReturnValue("2 KB");
    mockedFormatSize.mockClear();
    toLocaleStringSpy = jest
      .spyOn(Date.prototype, "toLocaleString")
      .mockImplementation(function (this: Date) {
        return `formatted:${this.toISOString()}`;
      });
  });

  afterEach(() => {
    toLocaleStringSpy.mockRestore();
  });

  it("renders the translated format, both dates, the formatted size and the author", () => {
    const html = renderToStaticMarkup(<ItemInfo item={buildItem()} />);

    expect(mockedGetFormatTranslationKey).toHaveBeenCalledWith(
      expect.objectContaining({ id: "item-1" }),
    );
    expect(mockedFormatSize).toHaveBeenCalledWith(2048, expect.any(Function));
    expect(html).toContain("translated:explorer.rightPanel.format");
    expect(html).toContain("translated:mime.pdf");
    expect(html).toContain("translated:explorer.rightPanel.updated_at");
    expect(html).toContain("formatted:2026-03-30T12:00:00.000Z");
    expect(html).toContain("translated:explorer.rightPanel.created_at");
    expect(html).toContain("formatted:2026-03-29T08:30:00.000Z");
    expect(html).toContain("translated:explorer.rightPanel.size");
    expect(html).toContain("2 KB");
    expect(html).toContain("translated:explorer.rightPanel.created_by");
    expect(html).toContain("Jane Doe");
  });

  it("omits the size row when the item size is missing or zero", () => {
    const html = renderToStaticMarkup(
      <ItemInfo
        item={buildItem({
          size: 0,
          created_at: undefined as never,
        })}
      />,
    );

    expect(mockedFormatSize).not.toHaveBeenCalled();
    expect(html).not.toContain("translated:explorer.rightPanel.size");
    expect(html).toContain("translated:explorer.rightPanel.created_at");
  });
});
