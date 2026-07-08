import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemsBrowseExplorer } from "@/features/explorer/components/items-browse/ItemsBrowseExplorer";
import { DefaultRoute } from "@/utils/defaultRoutes";
import WorkspacesExplorer from "../WorkspacesExplorer";

jest.mock("@/features/explorer/components/items-browse/ItemsBrowseExplorer", () => ({
  ItemsBrowseExplorer: jest.fn(() => <div>items-browse-explorer</div>),
}));

const mockedItemsBrowseExplorer = jest.mocked(ItemsBrowseExplorer);

describe("WorkspacesExplorer", () => {
  beforeEach(() => {
    mockedItemsBrowseExplorer.mockClear();
  });

  it("delegates filtered items browse to the canonical explorer host", () => {
    const html = renderToStaticMarkup(
      <WorkspacesExplorer defaultFilters={{ is_creator_me: true }} />,
    );

    expect(html).toContain("items-browse-explorer");
    expect(mockedItemsBrowseExplorer.mock.calls[0]?.[0]).toEqual({
      kind: "items",
      defaultFilters: { is_creator_me: true },
      showFilters: true,
      viewConfigKey: DefaultRoute.MY_FILES,
    });
  });

  it("forwards an explicit showFilters override unchanged", () => {
    renderToStaticMarkup(
      <WorkspacesExplorer
        defaultFilters={{ is_favorite: true }}
        showFilters={false}
      />,
    );

    expect(mockedItemsBrowseExplorer.mock.calls[0]?.[0]).toEqual({
      kind: "items",
      defaultFilters: { is_favorite: true },
      showFilters: false,
      viewConfigKey: DefaultRoute.MY_FILES,
    });
  });
});
