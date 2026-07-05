import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  type Item,
} from "@/features/drivers/types";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { LastItemBreadcrumb } from "../EmbeddedExplorerGridBreadcrumbs";

const renderedButtons: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
  ["data-testid"]?: string;
}> = [];

let shareModalIsOpen = false;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {
      language: "en",
    },
  }),
}));

jest.mock("next/router", () => ({
  useRouter: () => ({
    pathname: "/explorer/items/my-files",
    push: jest.fn(),
  }),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: () => ({
    user: undefined,
  }),
}));

jest.mock("../../../hooks/useBreadcrumb", () => ({
  useBreadcrumbQuery: () => ({
    data: [],
  }),
}));

jest.mock("../../../hooks/useQueries", () => ({
  useItem: () => ({
    data: undefined,
  }),
}));

jest.mock("../../../utils/utils", () => ({
  clearFromRoute: jest.fn(),
  getFromRoute: jest.fn(() => null),
  getManualNavigationItemId: jest.fn(() => null),
}));

jest.mock("../../item-actions/ItemActionDropdown", () => ({
  ItemActionDropdown: ({ trigger }: { trigger: React.ReactNode }) => <div>{trigger}</div>,
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: () => <div>icon</div>,
  IconSize: {
    SMALL: "small",
    MEDIUM: "medium",
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    onClick?: () => void;
    ["data-testid"]?: string;
  }) => {
    renderedButtons.push(props);
    return <button>{props.children}</button>;
  },
  useModal: jest.fn(),
}));

jest.mock("@/utils/defaultRoutes", () => ({
  DefaultRoute: {
    MY_FILES: "my-files",
    SHARED_WITH_ME: "shared-with-me",
  },
  getDefaultRoute: () => null,
  ORDERED_DEFAULT_ROUTES: [],
}));

jest.mock("../../modals/share/ItemShareModal", () => ({
  ItemShareModal: ({ item }: { item: Item }) => (
    <div data-testid="item-share-modal">{item.id}</div>
  ),
}));

const mockedUseModal = jest.mocked(useModal);

const buildItem = (): Item => ({
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
  computed_link_reach: LinkReach.PUBLIC,
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
});

describe("LastItemBreadcrumb", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
    shareModalIsOpen = false;
    mockedUseModal.mockImplementation(
      () =>
        ({
          isOpen: shareModalIsOpen,
          open: () => {
            shareModalIsOpen = true;
          },
          close: () => {
            shareModalIsOpen = false;
          },
        }) as never,
    );
  });

  it("opens the standard item share modal from the breadcrumb share button", () => {
    const item = buildItem();

    const htmlBefore = renderToStaticMarkup(<LastItemBreadcrumb item={item} />);
    const shareButton = renderedButtons.find(
      (button) => button["data-testid"] === "share-button",
    );

    expect(htmlBefore).not.toContain("data-testid=\"item-share-modal\"");

    shareButton?.onClick?.();

    const htmlAfter = renderToStaticMarkup(<LastItemBreadcrumb item={item} />);

    expect(htmlAfter).toContain("data-testid=\"item-share-modal\"");
  });
});
