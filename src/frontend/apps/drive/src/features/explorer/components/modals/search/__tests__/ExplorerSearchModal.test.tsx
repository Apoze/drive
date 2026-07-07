import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, type Item } from "@/features/drivers/types";
import { ExplorerSearchModal } from "../ExplorerSearchModal";
import { useExplorerSearchController } from "../useExplorerSearchController";
import { useAuth } from "@/features/auth/Auth";

const renderedButtonProps: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
}> = [];
const quickSearchGroupProps: Array<{
  onSelect: (item: Item) => void;
  group: {
    elements: Item[];
  };
}> = [];
const renderedModalTitles: string[] = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => {
    renderedButtonProps.push(props);
    return <button>{props.children}</button>;
  },
  Modal: ({
    title,
    children,
  }: {
    title?: string;
    children?: React.ReactNode;
  }) => {
    if (title) {
      renderedModalTitles.push(title);
    }
    return <div>{children}</div>;
  },
  ModalSize: {
    MEDIUM: "medium",
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  QuickSearch: ({
    children,
    placeholder,
  }: {
    children?: React.ReactNode;
    placeholder?: string;
  }) => <div data-placeholder={placeholder}>{children}</div>,
  QuickSearchGroup: (props: {
    onSelect: (item: Item) => void;
    group: {
      elements: Item[];
    };
  }) => {
    quickSearchGroupProps.push(props);
    return <div>quick-search-group</div>;
  },
  QuickSearchItemTemplate: ({
    left,
    right,
  }: {
    left?: React.ReactNode;
    right?: React.ReactNode;
  }) => (
    <div>
      {left}
      {right}
    </div>
  ),
  SmartScroller: ({
    children,
  }: {
    children?: React.ReactNode;
  }) => <div>{children}</div>,
}));

jest.mock("@/features/explorer/components/filters", () => ({
  ALL: "all",
  ExplorerFilterCategory: () => <div>filter-category</div>,
  ExplorerFilterContact: () => <div>filter-contact</div>,
  ExplorerFilterLocation: () => <div>filter-location</div>,
  ExplorerFilterModified: () => <div>filter-modified</div>,
}));

jest.mock("../../../icons/ItemIcon", () => ({
  ItemIcon: () => <div>item-icon</div>,
}));

jest.mock("../useExplorerSearchController", () => ({
  useExplorerSearchController: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

const mockedUseExplorerSearchController = jest.mocked(
  useExplorerSearchController,
);
const mockedUseAuth = jest.mocked(useAuth);

const buildItem = (): Item =>
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
    updated_at: new Date("2026-03-22T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-22T00:00:00Z"),
    path: "/Report.txt",
    abilities: {
      accesses_manage: false,
      accesses_view: true,
      children_create: false,
      children_list: false,
      destroy: true,
      favorite: false,
      invite_owner: false,
      link_configuration: false,
      media_auth: false,
      move: true,
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
      upload_ended: false,
    },
  }) as Item;

describe("ExplorerSearchModal", () => {
  beforeEach(() => {
    renderedButtonProps.length = 0;
    quickSearchGroupProps.length = 0;
    renderedModalTitles.length = 0;
    mockedUseAuth.mockReturnValue({
      user: {
        id: "user-1",
      },
    } as never);
  });

  it("renders the canonical modal shell and search filters from the controller", () => {
    mockedUseExplorerSearchController.mockReturnValue({
      inputValue: "",
      loading: false,
      items: [],
      filters: {},
      isMinimalLayout: false,
      showResetFilters: false,
      onInputChange: jest.fn(),
      onFilterChange: jest.fn(),
      onModifiedChange: jest.fn(),
      onResetFilters: jest.fn(),
      onItemClick: jest.fn(),
      bindContainerRef: jest.fn(),
    });

    const html = renderToStaticMarkup(
      <ExplorerSearchModal isOpen={true} onClose={jest.fn()} />,
    );

    expect(renderedModalTitles).toEqual(["explorer.search.modal.title"]);
    expect(html).toContain("data-placeholder=\"explorer.search.modal.placeholder\"");
    expect(html).toContain("filter-location");
    expect(html).toContain("filter-category");
    expect(html).toContain("filter-contact");
    expect(html).toContain("filter-modified");
    expect(html).not.toContain("explorer.search.modal.filters.reset");
  });

  it("wires reset and result activation through the controller", () => {
    const onResetFilters = jest.fn();
    const onItemClick = jest.fn();
    const resultItem = buildItem();

    mockedUseExplorerSearchController.mockReturnValue({
      inputValue: "report",
      loading: false,
      items: [resultItem],
      filters: {
        workspace: "workspace-1",
      },
      isMinimalLayout: false,
      showResetFilters: true,
      onInputChange: jest.fn(),
      onFilterChange: jest.fn(),
      onModifiedChange: jest.fn(),
      onResetFilters,
      onItemClick,
      bindContainerRef: jest.fn(),
    });

    const html = renderToStaticMarkup(
      <ExplorerSearchModal isOpen={true} onClose={jest.fn()} />,
    );

    const resetButton = renderedButtonProps.find(
      (button) => button.children === "explorer.search.modal.filters.reset",
    );

    resetButton?.onClick?.();
    quickSearchGroupProps[0]?.onSelect(resultItem);

    expect(html).toContain("quick-search-group");
    expect(onResetFilters).toHaveBeenCalled();
    expect(onItemClick).toHaveBeenCalledWith(resultItem);
  });
});
