import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import { ItemsBrowseExplorer } from "../ItemsBrowseExplorer";
import { useInfiniteChildren } from "@/features/explorer/hooks/useInfiniteChildren";
import {
  useInfiniteItems,
  useInfiniteRecentItems,
} from "@/features/explorer/hooks/useInfiniteItems";
import { BrowseExplorerTemplate } from "@/features/explorer/components/shared-browse/BrowseExplorerTemplate";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";

jest.mock("@/features/explorer/hooks/useInfiniteChildren", () => ({
  useInfiniteChildren: jest.fn(),
}));

jest.mock("@/features/explorer/hooks/useInfiniteItems", () => ({
  useInfiniteItems: jest.fn(),
  useInfiniteRecentItems: jest.fn(),
}));

jest.mock("@/features/explorer/components/GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("@/features/ui/preview/custom-files-preview/CustomFilesPreview", () => ({
  CustomFilesPreview: ({
    currentItem,
    items,
  }: {
    currentItem?: { title?: string };
    items: Array<{ title?: string }>;
  }) => (
    <div data-testid="items-preview-host">
      {currentItem?.title ?? "no-current-item"}:{items.map((item) => item.title).join(",")}
    </div>
  ),
}));

jest.mock(
  "@/features/explorer/components/shared-browse/BrowseExplorerTemplate",
  () => ({
    BrowseExplorerTemplate: jest.fn(({ renderAfterExplorer }) => (
      <div>
        <div>browse-template</div>
        {renderAfterExplorer?.([
          {
            id: "child-1",
            title: "Report",
            type: ItemType.FILE,
          },
        ])}
      </div>
    )),
  }),
);

const mockedUseInfiniteChildren = jest.mocked(useInfiniteChildren);
const mockedUseInfiniteItems = jest.mocked(useInfiniteItems);
const mockedUseInfiniteRecentItems = jest.mocked(useInfiniteRecentItems);
const mockedBrowseExplorerTemplate = jest.mocked(BrowseExplorerTemplate);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);

describe("ItemsBrowseExplorer", () => {
  beforeEach(() => {
    mockedUseInfiniteChildren.mockReset();
    mockedUseInfiniteItems.mockReset();
    mockedUseInfiniteRecentItems.mockReset();
    mockedBrowseExplorerTemplate.mockClear();
    mockedUseGlobalExplorer.mockReturnValue({
      previewItem: {
        id: "preview-1",
        title: "Preview report",
      },
      previewItems: [
        {
          id: "preview-1",
          title: "Preview report",
        },
      ],
      setPreviewCurrentItem: jest.fn(),
      replacePreviewItems: jest.fn(),
    } as never);
  });

  it("routes recent browse through the shared browse template", () => {
    const defaultFilters = { type: ItemType.FILE };
    const recentResult = {
      data: {
        pages: [],
      },
      fetchNextPage: jest.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    };

    mockedUseInfiniteRecentItems.mockReturnValue(recentResult as never);

    renderToStaticMarkup(
      <ItemsBrowseExplorer kind="recent" defaultFilters={defaultFilters} />,
    );

    expect(mockedUseInfiniteRecentItems).toHaveBeenCalledWith(defaultFilters);
    expect(mockedUseInfiniteItems).not.toHaveBeenCalled();
    expect(mockedBrowseExplorerTemplate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: recentResult.data,
        filters: defaultFilters,
        hasNextPage: recentResult.hasNextPage,
        isFetchingNextPage: recentResult.isFetchingNextPage,
        isLoading: recentResult.isLoading,
        showFilters: true,
      }),
      undefined,
    );
  });

  it("hosts the items preview through renderAfterExplorer using global preview state", () => {
    const childrenResult = {
      data: {
        pages: [],
      },
      fetchNextPage: jest.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    };

    mockedUseInfiniteChildren.mockReturnValue(childrenResult as never);

    const html = renderToStaticMarkup(
      <ItemsBrowseExplorer kind="children" itemId="folder-1" />,
    );

    expect(mockedBrowseExplorerTemplate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: childrenResult.data,
        renderAfterExplorer: expect.any(Function),
      }),
      undefined,
    );
    expect(html).toContain("data-testid=\"items-preview-host\"");
    expect(html).toContain("Preview report:Preview report");
  });
});
