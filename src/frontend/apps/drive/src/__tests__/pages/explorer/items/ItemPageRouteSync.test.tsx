import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/router";

const renderedItemIds: Array<string | null> = [];

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("@/features/layouts/components/explorer/ExplorerLayout", () => ({
  getGlobalExplorerLayout: jest.fn(),
}));

jest.mock("@/features/explorer/components/items-browse/ItemsBrowseExplorer", () => ({
  ItemsBrowseExplorer: ({
    itemId,
  }: {
    itemId: string | null;
  }) => {
    renderedItemIds.push(itemId);
    return <div data-testid="items-browse-explorer">{itemId ?? "no-item-id"}</div>;
  },
}));

import ItemPage from "@/pages/explorer/items/[id]";

const mockedUseRouter = jest.mocked(useRouter);

describe("pages/explorer/items/[id] route sync", () => {
  beforeEach(() => {
    renderedItemIds.length = 0;
  });

  it("rebinds the canonical items browse surface to the current route id on rerender", () => {
    mockedUseRouter.mockReturnValue({
      query: {
        id: "folder-1",
      },
    } as never);

    const firstHtml = renderToStaticMarkup(<ItemPage />);

    mockedUseRouter.mockReturnValue({
      query: {
        id: "folder-2",
      },
    } as never);

    const secondHtml = renderToStaticMarkup(<ItemPage />);

    expect(renderedItemIds).toEqual(["folder-1", "folder-2"]);
    expect(firstHtml).toContain("folder-1");
    expect(secondHtml).toContain("folder-2");
  });
});
