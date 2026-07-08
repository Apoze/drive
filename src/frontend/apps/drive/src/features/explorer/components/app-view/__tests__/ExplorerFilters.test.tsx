import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ExplorerFilters,
  ExplorerFilterScope,
  ExplorerFilterType,
  ExplorerFilterWorkspace,
} from "../ExplorerFilters";
import { useAppExplorer } from "../AppExplorer";
import { useItems } from "../../../hooks/useQueries";
import { useAuth } from "@/features/auth/Auth";
import { useContacts, useUsers } from "@/features/users/hooks/useUserQueries";

const renderedFilterProps: Array<{
  label?: string;
  options?: Array<{ value?: string; label?: string }>;
  selectedKey?: string | null;
  onSelectionChange?: (value: string | null) => void;
  value?: string | null;
  onChange?: (value: string | null) => void;
  isDisabled?: boolean;
}> = [];
const renderedSearchFilterProps: Array<{
  label?: string;
  isActive?: boolean;
  onItemSelect?: (item?: { id: string; label: string }) => void;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  FileIcon: () => <div>file-icon</div>,
  Filter: (props: {
    label?: string;
    options?: Array<{ value?: string; label?: string }>;
    selectedKey?: string | null;
    onSelectionChange?: (value: string | null) => void;
    value?: string | null;
    onChange?: (value: string | null) => void;
    isDisabled?: boolean;
  }) => {
    renderedFilterProps.push(props);
    return <div>{props.label}</div>;
  },
  IconSize: {
    SMALL: "small",
  },
  SmartScroller: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
  useResponsive: () => ({
    isDesktop: true,
    isMobile: false,
    isTablet: false,
  }),
  UserSearchFilter: (props: {
    label?: string;
    isActive?: boolean;
    onItemSelect?: (item?: { id: string; label: string }) => void;
  }) => {
    renderedSearchFilterProps.push(props);
    return <div>{props.label}</div>;
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  CalendarRange: () => <div>calendar-range</div>,
}));

jest.mock("../AppExplorer", () => ({
  useAppExplorer: jest.fn(),
}));

jest.mock("../../../hooks/useQueries", () => ({
  useItems: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/features/users/hooks/useUserQueries", () => ({
  useContacts: jest.fn(),
  useUsers: jest.fn(),
}));

jest.mock("../../icons/ItemIcon", () => ({
  ItemIcon: () => <div>item-icon</div>,
}));

const mockedUseAppExplorer = jest.mocked(useAppExplorer);
const mockedUseItems = jest.mocked(useItems);
const mockedUseAuth = jest.mocked(useAuth);
const mockedUseContacts = jest.mocked(useContacts);
const mockedUseUsers = jest.mocked(useUsers);

describe("ExplorerFilters", () => {
  beforeEach(() => {
    renderedFilterProps.length = 0;
    renderedSearchFilterProps.length = 0;
    mockedUseAppExplorer.mockReturnValue({
      filters: {},
      onFiltersChange: jest.fn(),
    } as never);
    mockedUseItems.mockReturnValue({
      data: [
        {
          id: "workspace-1",
          title: "Workspace",
        },
      ],
    } as never);
    mockedUseAuth.mockReturnValue({
      user: {
        id: "user-1",
      },
    } as never);
    mockedUseContacts.mockReturnValue({
      data: [],
      isLoading: false,
    } as never);
    mockedUseUsers.mockReturnValue({
      data: [],
      isLoading: false,
    } as never);
  });

  it("routes filter changes through the canonical ExplorerFilters host", () => {
    const onFiltersChange = jest.fn();
    mockedUseAppExplorer.mockReturnValue({
      filters: {
        category: "pdf",
      },
      onFiltersChange,
    } as never);

    renderToStaticMarkup(<ExplorerFilters />);

    renderedFilterProps[0]?.onSelectionChange?.("image");
    renderedFilterProps[0]?.onSelectionChange?.(null);
    renderedSearchFilterProps[0]?.onItemSelect?.({
      id: "contact-1",
      label: "Contact",
    });

    expect(renderedFilterProps[0]).toMatchObject({
      label: "explorer.filters.category.label",
      selectedKey: "pdf",
    });
    expect(onFiltersChange).toHaveBeenNthCalledWith(1, {
      category: "image",
    });
    expect(onFiltersChange).toHaveBeenNthCalledWith(2, {});
    expect(onFiltersChange).toHaveBeenNthCalledWith(3, {
      category: "pdf",
      contact: "contact-1",
    });
  });

  it("keeps the type, workspace and scope filter options stable", () => {
    renderToStaticMarkup(
      <>
        <ExplorerFilterType value={null} onChange={jest.fn()} />
        <ExplorerFilterWorkspace
          value={null}
          onChange={jest.fn()}
          isDisabled={true}
        />
        <ExplorerFilterScope value={null} onChange={jest.fn()} />
      </>,
    );

    expect(renderedFilterProps[0]?.options).toHaveLength(3);
    expect(renderedFilterProps[1]).toMatchObject({
      label: "explorer.filters.folders.label",
      isDisabled: true,
    });
    expect(renderedFilterProps[1]?.options).toHaveLength(2);
    expect(renderedFilterProps[2]).toMatchObject({
      label: "explorer.filters.scopes.label",
    });
    expect(renderedFilterProps[2]?.options).toHaveLength(2);
  });
});
