import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ExplorerRightPanelContent } from "../ExplorerRightPanelContent";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  type Item,
} from "@/features/drivers/types";
import { useGlobalExplorer } from "../../GlobalExplorerContext";
import { createAndCopyMountShareLink } from "@/features/mounts/utils/mountShareLink";
import {
  SelectionStore,
  SelectionStoreContext,
} from "@/features/explorer/stores/selectionStore";

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

jest.mock("@gouvfr-lasuite/cunningham-react", () => {
  const actual = jest.requireActual("@gouvfr-lasuite/cunningham-react");

  return {
    ...actual,
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
  };
});

jest.mock("@/features/explorer/components/GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("@/features/ui/components/info/InfoRow", () => ({
  InfoRow: ({
    label,
    rightContent,
  }: {
    label: React.ReactNode;
    rightContent?: React.ReactNode;
  }) => (
    <div>
      <div>{label}</div>
      <div>{rightContent}</div>
    </div>
  ),
}));

jest.mock("../../icons/ItemIcon", () => ({
  ItemIcon: () => <div>item-icon</div>,
}));

jest.mock("@/features/items/components/ItemInfo", () => ({
  ItemInfo: ({ item }: { item: Item }) => <div>{item.title}</div>,
}));

jest.mock("../../modals/share/ItemShareModal", () => ({
  ItemShareModal: ({ item }: { item: Item }) => (
    <div data-testid="item-share-modal">{item.title}</div>
  ),
}));

jest.mock("@/features/mounts/utils/mountShareLink", () => ({
  createAndCopyMountShareLink: jest.fn(),
}));

const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedCreateAndCopyMountShareLink = jest.mocked(createAndCopyMountShareLink);

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
    update: false,
    upload_ended: false,
  },
  ...overrides,
});

const renderPanel = (item: Item) => {
  renderedButtons.length = 0;
  return renderToStaticMarkup(
    <SelectionStoreContext.Provider value={new SelectionStore()}>
      <ExplorerRightPanelContent item={item} />
    </SelectionStoreContext.Provider>,
  );
};

describe("ExplorerRightPanelContent", () => {
  beforeEach(() => {
    modalIsOpen = false;
    renderedButtons.length = 0;
    mockedUseGlobalExplorer.mockReturnValue({
      closeRightPanel: jest.fn(),
      selectedItems: [],
    } as never);
    mockedCreateAndCopyMountShareLink.mockReset();
  });

  it("shows a share action for mount items and routes it through the shared helper", () => {
    const mountItem = {
      ...buildItem({
        abilities: {
          ...buildItem().abilities,
          accesses_view: false,
        },
      }),
      mountMeta: {
        mountId: "mount-1",
        normalizedPath: "/Report.txt",
        entryType: "file" as const,
        mountTitle: "Shared Docs",
        provider: "localfs",
        abilities: {
          children_list: false,
          create_folder: false,
          move: false,
          rename: false,
          destroy: false,
          upload: false,
          duplicate: false,
          download: false,
          preview: false,
          wopi: false,
          share_link_create: true,
        },
      },
    };

    const html = renderPanel(mountItem as never);
    const shareButton = renderedButtons.find(
      (button) => button.children === "explorer.rightPanel.share",
    );

    expect(html).toContain("explorer.rightPanel.share");
    expect(shareButton).toBeDefined();

    shareButton?.onClick?.();

    expect(mockedCreateAndCopyMountShareLink).toHaveBeenCalledWith(mountItem);
  });

  it("keeps the standard item share modal flow for regular items", () => {
    const item = buildItem();

    const htmlBeforeOpen = renderPanel(item);
    const shareButton = renderedButtons.find(
      (button) => button.children === "explorer.rightPanel.share",
    );

    expect(htmlBeforeOpen).toContain("explorer.rightPanel.share");

    shareButton?.onClick?.();

    const htmlAfterOpen = renderPanel(item);

    expect(mockedCreateAndCopyMountShareLink).not.toHaveBeenCalled();
    expect(htmlAfterOpen).toContain("data-testid=\"item-share-modal\"");
  });

  it("routes the close button through the explicit right-panel API", () => {
    const closeRightPanel = jest.fn();
    const item = buildItem();

    mockedUseGlobalExplorer.mockReturnValue({
      closeRightPanel,
      selectedItems: [],
    } as never);

    renderPanel(item);

    renderedButtons[0]?.onClick?.();

    expect(closeRightPanel).toHaveBeenCalled();
  });
});
