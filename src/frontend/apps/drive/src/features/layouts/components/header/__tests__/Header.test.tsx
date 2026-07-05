import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, type Item } from "@/features/drivers/types";
import { HeaderRight } from "../Header";
import { useAuth } from "@/features/auth/Auth";
import { useResponsive } from "@gouvfr-lasuite/ui-kit";
import { useIsMinimalLayout } from "@/utils/useLayout";

const renderedSearchProps: Array<{
  defaultFilters?: Record<string, string>;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {
      changeLanguage: jest.fn().mockResolvedValue(undefined),
    },
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  useResponsive: jest.fn(),
  LanguagePicker: () => <div>language-picker</div>,
}));

jest.mock("@/utils/useLayout", () => ({
  useIsMinimalLayout: jest.fn(),
}));

jest.mock("@/features/explorer/components/app-view/ExplorerSearchButton", () => ({
  ExplorerSearchButton: (props: { defaultFilters?: Record<string, string> }) => {
    renderedSearchProps.push(props);
    return <div>search-button</div>;
  },
}));

jest.mock("@/features/feedback/Feedback", () => ({
  Feedback: () => <div>feedback</div>,
}));

jest.mock("@/features/ui/components/gaufre/Gaufre", () => ({
  Gaufre: () => <div>gaufre</div>,
}));

jest.mock("@/features/ui/components/user/UserProfile", () => ({
  UserProfile: () => <div>user-profile</div>,
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: () => ({
    updateUser: jest.fn(),
  }),
}));

const mockedUseAuth = jest.mocked(useAuth);
const mockedUseResponsive = jest.mocked(useResponsive);
const mockedUseIsMinimalLayout = jest.mocked(useIsMinimalLayout);

const buildItem = (): Item =>
  ({
    id: "folder-2",
    title: "Workspace folder",
    filename: "Workspace folder",
    creator: {
      id: "user-1",
      full_name: "Jane Doe",
      short_name: "JD",
    },
    type: ItemType.FOLDER,
    parents: [
      ({
        id: "workspace-1",
      } as unknown as Item),
    ],
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-22T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-22T00:00:00Z"),
    path: "/Workspace folder",
    abilities: {} as never,
  }) as Item;

describe("HeaderRight", () => {
  beforeEach(() => {
    renderedSearchProps.length = 0;
    mockedUseAuth.mockReturnValue({
      user: {
        id: "user-1",
      },
    } as never);
    mockedUseResponsive.mockReturnValue({
      isTablet: false,
    } as never);
  });

  it("passes the minimal-layout default workspace filter to the search host", () => {
    mockedUseIsMinimalLayout.mockReturnValue(true);

    renderToStaticMarkup(
      <HeaderRight displaySearch currentItem={buildItem()} />,
    );

    expect(renderedSearchProps).toEqual([
      {
        defaultFilters: {
          workspace: "workspace-1",
        },
      },
    ]);
  });

  it("keeps search unscoped outside minimal layout", () => {
    mockedUseIsMinimalLayout.mockReturnValue(false);

    renderToStaticMarkup(
      <HeaderRight displaySearch currentItem={buildItem()} />,
    );

    expect(renderedSearchProps).toEqual([
      {
        defaultFilters: {},
      },
    ]);
  });
});
