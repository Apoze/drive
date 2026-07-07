import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/router";
import { useAuth } from "@/features/auth/Auth";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import {
  ExplorerLayout,
  ExplorerPanelsLayout,
} from "../ExplorerLayout";
import { setManualNavigationItemId } from "@/features/explorer/utils/utils";

const renderedMainLayoutProps: Array<{
  rightPanelIsOpen?: boolean;
  hideLeftPanelOnDesktop?: boolean;
  onToggleRightPanel?: () => void;
  setIsLeftPanelOpen?: () => void;
}> = [];
const renderedProviderProps: Array<{
  itemId?: string;
  displayMode?: string;
  onNavigate?: (event: { item: unknown }) => void;
}> = [];

const mockRouterPush = jest.fn();
const mockSetRightPanelOpen = jest.fn();
const mockSetIsLeftPanelOpen = jest.fn();

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  MainLayout: (props: {
    children?: React.ReactNode;
    leftPanelContent?: React.ReactNode;
    rightPanelContent?: React.ReactNode;
    rightHeaderContent?: React.ReactNode;
    icon?: React.ReactNode;
    rightPanelIsOpen?: boolean;
    hideLeftPanelOnDesktop?: boolean;
    onToggleRightPanel?: () => void;
    setIsLeftPanelOpen?: () => void;
  }) => {
    renderedMainLayoutProps.push(props);
    return (
      <div>
        {props.icon}
        {props.rightHeaderContent}
        {props.leftPanelContent}
        {props.rightPanelContent}
        {props.children}
      </div>
    );
  },
}));

jest.mock("@/features/explorer/components/tree/ExplorerTree", () => ({
  ExplorerTree: () => <div>explorer-tree</div>,
}));

jest.mock("../../left-panel/LeftPanelMobile", () => ({
  LeftPanelMobile: () => <div>left-panel-mobile</div>,
}));

jest.mock("../../header/Header", () => ({
  HeaderIcon: () => <div>header-icon</div>,
  HeaderRight: () => <div>header-right</div>,
}));

jest.mock("@/features/explorer/components/right-panel/ExplorerRightPanelContent", () => ({
  ExplorerRightPanelContent: () => <div>right-panel</div>,
}));

jest.mock("@/features/explorer/components/GlobalExplorerContext", () => ({
  GlobalExplorerProvider: (props: {
    children?: React.ReactNode;
    itemId?: string;
    displayMode?: string;
    onNavigate?: (event: { item: unknown }) => void;
  }) => {
    renderedProviderProps.push(props);
    return <div>{props.children}</div>;
  },
  useGlobalExplorer: jest.fn(),
}));

jest.mock("@/features/layouts/hooks/useSyncUserLanguage", () => ({
  useSyncUserLanguage: jest.fn(),
}));

jest.mock("@/features/ui/components/release-note", () => ({
  ReleaseNoteAuto: () => null,
}));

jest.mock("@/features/explorer/utils/utils", () => ({
  setManualNavigationItemId: jest.fn(),
}));

const mockedUseRouter = jest.mocked(useRouter);
const mockedUseAuth = jest.mocked(useAuth);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedSetManualNavigationItemId = jest.mocked(setManualNavigationItemId);

describe("ExplorerLayout family", () => {
  beforeEach(() => {
    renderedMainLayoutProps.length = 0;
    renderedProviderProps.length = 0;
    mockRouterPush.mockReset();
    mockSetRightPanelOpen.mockReset();
    mockSetIsLeftPanelOpen.mockReset();
    mockedSetManualNavigationItemId.mockReset();
    mockedUseRouter.mockReturnValue({
      query: {
        id: "folder-1",
        minimal: "true",
        ignored: "value",
      },
      push: mockRouterPush,
    } as never);
    mockedUseAuth.mockReturnValue({
      user: {
        id: "user-1",
      },
    } as never);
    mockedUseGlobalExplorer.mockReturnValue({
      rightPanelOpen: true,
      setRightPanelOpen: mockSetRightPanelOpen,
      item: {
        id: "folder-1",
      },
      rightPanelForcedItem: undefined,
      isLeftPanelOpen: false,
      setIsLeftPanelOpen: mockSetIsLeftPanelOpen,
    } as never);
  });

  it("keeps explorer navigation scoped to the minimal query and canonical item route", () => {
    renderToStaticMarkup(
      <ExplorerLayout>
        <div>content</div>
      </ExplorerLayout>,
    );

    renderedProviderProps[0]?.onNavigate?.({
      item: {
        id: "item-1",
        originalId: "favorite-1",
      },
    });

    expect(renderedProviderProps[0]).toMatchObject({
      itemId: "folder-1",
      displayMode: "app",
    });
    expect(mockedSetManualNavigationItemId).toHaveBeenCalledWith("favorite-1");
    expect(mockRouterPush).toHaveBeenCalledWith({
      id: "favorite-1",
      pathname: "/explorer/items/[id]",
      query: {
        id: "favorite-1",
        minimal: "true",
      },
    });
  });

  it("keeps the canonical desktop shell wiring when a user is present", () => {
    const html = renderToStaticMarkup(
      <ExplorerPanelsLayout isMinimalLayout={false}>
        <div>content</div>
      </ExplorerPanelsLayout>,
    );

    renderedMainLayoutProps[0]?.onToggleRightPanel?.();
    renderedMainLayoutProps[0]?.setIsLeftPanelOpen?.();

    expect(html).toContain("explorer-tree");
    expect(renderedMainLayoutProps[0]).toMatchObject({
      rightPanelIsOpen: true,
      hideLeftPanelOnDesktop: false,
    });
    expect(mockSetRightPanelOpen).toHaveBeenCalledWith(false);
    expect(mockSetIsLeftPanelOpen).toHaveBeenCalledWith(true);
  });

  it("falls back to the mobile left panel host when there is no authenticated user", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
    } as never);

    const html = renderToStaticMarkup(
      <ExplorerPanelsLayout isMinimalLayout={false}>
        <div>content</div>
      </ExplorerPanelsLayout>,
    );

    expect(html).toContain("left-panel-mobile");
    expect(renderedMainLayoutProps[0]).toMatchObject({
      hideLeftPanelOnDesktop: true,
    });
  });
});
