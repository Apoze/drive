import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useQuery } from "@tanstack/react-query";
import { EmbeddedExplorer } from "../EmbeddedExplorer";
import { createEmbeddedExplorerNavigationController } from "../embeddedExplorerNavigationController";
import { useState } from "react";

const embeddedExplorerGridProps: Array<{
  onNavigate?: (event: { item: { id: string } }) => void;
  items?: Array<{ id: string }>;
}> = [];
const embeddedExplorerBreadcrumbsProps: Array<{
  goToSpaces?: () => void;
  onGoBack?: (item: { id: string }) => void;
  forcedBreadcrumbsItems?: Array<{ id: string; title: string }>;
}> = [];
const embeddedSearchInputProps: Array<{
  onSearch?: (query: string) => void;
  value?: string;
}> = [];

jest.mock("react", () => {
  const actual = jest.requireActual("react");

  return {
    ...actual,
    useState: jest.fn(actual.useState),
  };
});

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: () => ({
    user: undefined,
  }),
}));

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(() => ({
    data: [],
    isLoading: false,
  })),
}));

jest.mock("../../../hooks/useInfiniteChildren", () => ({
  useInfiniteChildren: jest.fn(() => ({
    data: {
      pages: [
        {
          children: [{ id: "child-folder", title: "Child folder" }],
        },
      ],
    },
    isLoading: false,
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: jest.fn(),
  })),
}));

jest.mock("../../../hooks/useInfiniteItems", () => ({
  useInfiniteRecentItems: jest.fn(() => ({
    data: {
      pages: [{ children: [] }],
    },
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: jest.fn(),
  })),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(() => ({
    searchItems: jest.fn(() => []),
  })),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Spinner: () => <div>spinner</div>,
}));

jest.mock("@/features/ui/components/infinite-scroll/InfiniteScroll", () => ({
  InfiniteScroll: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock("../EmbeddedExplorerGrid", () => ({
  EmbeddedExplorerGrid: (props: {
    onNavigate?: (event: { item: { id: string } }) => void;
    items?: Array<{ id: string }>;
  }) => {
    embeddedExplorerGridProps.push(props);
    return <div>embedded-grid</div>;
  },
}));

jest.mock("../EmbeddedExplorerGridBreadcrumbs", () => ({
  EmbeddedExplorerGridBreadcrumbs: (props: {
    goToSpaces?: () => void;
    onGoBack?: (item: { id: string }) => void;
    forcedBreadcrumbsItems?: Array<{ id: string; title: string }>;
  }) => {
    embeddedExplorerBreadcrumbsProps.push(props);
    return <div>embedded-breadcrumbs</div>;
  },
}));

jest.mock("../EmbeddedExplorerSearchInput", () => ({
  EmbeddedExplorerSearchInput: (props: {
    onSearch?: (query: string) => void;
    value?: string;
  }) => {
    embeddedSearchInputProps.push(props);
    return <div>embedded-search</div>;
  },
}));

jest.mock("../embeddedExplorerNavigationController", () => ({
  createEmbeddedExplorerNavigationController: jest.fn(),
}));

jest.mock("../../GlobalExplorerContext", () => ({
  getOriginalIdFromTreeId: jest.fn((treeId: string) => {
    const parts = treeId.split("::");
    return parts[parts.length - 1];
  }),
}));

const mockedCreateEmbeddedExplorerNavigationController = jest.mocked(
  createEmbeddedExplorerNavigationController,
);
const mockedUseState = jest.mocked(useState);
const mockedUseQuery = jest.mocked(useQuery);
const asMockedStateTuple = (value: unknown) =>
  [value, jest.fn() as React.Dispatch<unknown>] as [unknown, React.Dispatch<unknown>];

describe("EmbeddedExplorer", () => {
  beforeEach(() => {
    embeddedExplorerGridProps.length = 0;
    embeddedExplorerBreadcrumbsProps.length = 0;
    embeddedSearchInputProps.length = 0;
    mockedCreateEmbeddedExplorerNavigationController.mockReset();
    mockedUseQuery.mockReset();
    mockedUseQuery.mockReturnValue({
      data: [],
      isLoading: false,
    } as never);
    mockedUseState.mockReset();
    mockedUseState
      .mockImplementationOnce((initial?: unknown) => asMockedStateTuple(initial))
      .mockImplementationOnce((initial?: unknown) => asMockedStateTuple(initial));
  });

  it("routes embedded grid and breadcrumbs navigation through the shared local controller", () => {
    const clearSelection = jest.fn();
    const setCurrentItemId = jest.fn();
    const navigateToItem = jest.fn();
    const navigateToRoot = jest.fn();
    const navigateToBreadcrumbItem = jest.fn();

    mockedCreateEmbeddedExplorerNavigationController.mockReturnValue({
      navigateToItem,
      navigateToRoot,
      navigateToBreadcrumbItem,
    });

    renderToStaticMarkup(
      <EmbeddedExplorer
        clearSelection={clearSelection}
        currentItemId="folder-0"
        setCurrentItemId={setCurrentItemId}
        showSearch={true}
      />,
    );

    embeddedExplorerGridProps[0]?.onNavigate?.({
      item: { id: "favorites::folder-1" },
    });
    embeddedExplorerBreadcrumbsProps[0]?.goToSpaces?.();
    embeddedExplorerBreadcrumbsProps[0]?.onGoBack?.({ id: "search" });
    embeddedExplorerBreadcrumbsProps[0]?.onGoBack?.({ id: "folder-2" });

    expect(
      mockedCreateEmbeddedExplorerNavigationController,
    ).toHaveBeenCalledWith({
      clearSelection,
      resetSearch: expect.any(Function),
      setCurrentItemId,
    });
    expect(navigateToItem).toHaveBeenCalledWith("folder-1");
    expect(navigateToRoot).toHaveBeenCalledTimes(1);
    expect(navigateToBreadcrumbItem).toHaveBeenNthCalledWith(1, "search");
    expect(navigateToBreadcrumbItem).toHaveBeenNthCalledWith(2, "folder-2");
  });

  it("keeps the embedded search host wired to search results and forced breadcrumbs", () => {
    mockedCreateEmbeddedExplorerNavigationController.mockReturnValue({
      navigateToItem: jest.fn(),
      navigateToRoot: jest.fn(),
      navigateToBreadcrumbItem: jest.fn(),
    });
    mockedUseState.mockReset();
    mockedUseState
      .mockImplementationOnce(() => asMockedStateTuple("report"))
      .mockImplementationOnce(() => asMockedStateTuple("report"));
    mockedUseQuery.mockReturnValue({
      data: [
        {
          id: "search-1",
          title: "Search result",
        },
      ],
      isLoading: false,
    } as never);

    renderToStaticMarkup(
      <EmbeddedExplorer
        currentItemId="folder-0"
        setCurrentItemId={jest.fn()}
        showSearch={true}
      />,
    );

    expect(embeddedSearchInputProps[0]).toMatchObject({
      value: "report",
    });
    expect(embeddedExplorerGridProps[0]?.items).toEqual([
      expect.objectContaining({
        id: "search-1",
      }),
    ]);
    expect(
      embeddedExplorerBreadcrumbsProps[0]?.forcedBreadcrumbsItems,
    ).toEqual([
      expect.objectContaining({
        id: "search",
        title: "Search results",
      }),
    ]);
  });
});
