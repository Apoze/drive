import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  type Item,
} from "@/features/drivers/types";
import { useRefreshItemCache } from "@/features/explorer/hooks/useRefreshItems";
import { CustomFilesPreview } from "../CustomFilesPreview";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

let modalIsOpen = false;
const renderedButtons: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
}> = [];
let capturedFilePreviewProps:
  | {
      onFileRename?: (file: { id: string }, newName: string) => void;
    }
  | undefined;

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => {
    renderedButtons.push({ children, onClick });
    return <button>{children}</button>;
  },
  useModal: () => ({
    isOpen: modalIsOpen,
    open: () => {
      modalIsOpen = true;
    },
    close: () => {
      modalIsOpen = false;
    },
  }),
}));

jest.mock("../../files-preview/FilesPreview", () => ({
  FilePreview: (props: {
    headerRightContent?: React.ReactNode;
    sidebarContent?: React.ReactNode;
    onFileRename?: (file: { id: string }, newName: string) => void;
  }) => {
    capturedFilePreviewProps = props;
    return (
      <div>
        <div data-testid="preview-header">{props.headerRightContent}</div>
        <div data-testid="preview-sidebar">{props.sidebarContent}</div>
      </div>
    );
  },
}));

jest.mock("../../files-preview/previewSource", () => ({
  defaultPreviewSource: { kind: "default-preview-source" },
}));

jest.mock("@/features/explorer/utils/utils", () => ({
  itemToPreviewFile: jest.fn((item: { id: string; title: string; filename: string }) => ({
    id: item.id,
    title: item.title,
    filename: item.filename,
  })),
}));

jest.mock("@/features/items/hooks/useDownloadItem", () => ({
  useDownloadItem: () => ({
    handleDownloadItem: jest.fn(),
  }),
}));

jest.mock("@/features/items/components/ItemInfo", () => ({
  ItemInfo: ({ item }: { item: Item }) => <div>{item.title}</div>,
}));

jest.mock("@/features/explorer/components/itemShareModalLauncher", () => ({
  ItemShareModalLauncher: ({
    isOpen,
    item,
  }: {
    isOpen: boolean;
    item?: Item | null;
  }) =>
    isOpen && item ? (
      <div data-testid="item-share-modal-launcher">{item.title}</div>
    ) : null,
}));

jest.mock("@/features/explorer/hooks/useRefreshItems", () => ({
  useRefreshItemCache: jest.fn(),
}));

const mockedUseRefreshItemCache = jest.mocked(useRefreshItemCache);

const buildItem = (overrides: Partial<Item> = {}): Item => ({
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
  upload_state: ItemUploadState.READY,
  updated_at: new Date("2026-03-22T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-22T00:00:00Z"),
  path: "/Report.txt",
  mimetype: "text/plain",
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
    update: true,
    upload_ended: false,
  },
  ...overrides,
});

describe("CustomFilesPreview", () => {
  beforeEach(() => {
    modalIsOpen = false;
    renderedButtons.length = 0;
    capturedFilePreviewProps = undefined;
    mockedUseRefreshItemCache.mockReset();
  });

  it("keeps the standard item share modal flow in preview through the shared launcher", () => {
    const refreshItemCache = jest.fn();
    mockedUseRefreshItemCache.mockReturnValue(refreshItemCache);
    const currentItem = buildItem();

    const htmlBeforeOpen = renderToStaticMarkup(
      <CustomFilesPreview currentItem={currentItem} items={[currentItem]} />,
    );
    const shareButton = renderedButtons.find(
      (button) => button.children === "explorer.rightPanel.share",
    );

    expect(htmlBeforeOpen).toContain("explorer.rightPanel.share");
    expect(shareButton).toBeDefined();

    shareButton?.onClick?.();

    const htmlAfterOpen = renderToStaticMarkup(
      <CustomFilesPreview currentItem={currentItem} items={[currentItem]} />,
    );

    expect(htmlAfterOpen).toContain("data-testid=\"item-share-modal-launcher\"");
  });

  it("keeps optimistic rename updates routed through the item adapter", () => {
    const refreshItemCache = jest.fn();
    mockedUseRefreshItemCache.mockReturnValue(refreshItemCache);
    const currentItem = buildItem();
    const siblingItem = buildItem({
      id: "item-2",
      title: "Notes",
      filename: "Notes.txt",
      path: "/Notes.txt",
    });
    const onItemsChange = jest.fn();

    renderToStaticMarkup(
      <CustomFilesPreview
        currentItem={currentItem}
        items={[currentItem, siblingItem]}
        onItemsChange={onItemsChange}
      />,
    );

    capturedFilePreviewProps?.onFileRename?.(
      { id: currentItem.id },
      "Report v2",
    );

    expect(onItemsChange).toHaveBeenCalledWith([
      expect.objectContaining({
        id: currentItem.id,
        title: "Report v2",
      }),
      expect.objectContaining({
        id: siblingItem.id,
        title: siblingItem.title,
      }),
    ]);
    expect(refreshItemCache).toHaveBeenCalledWith(currentItem.id, {
      title: "Report v2",
    });
  });
});
