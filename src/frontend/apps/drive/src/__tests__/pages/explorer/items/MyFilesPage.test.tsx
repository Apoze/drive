import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import WorkspacesExplorer from "@/features/explorer/components/workspaces-explorer/WorkspacesExplorer";
import MyFilesPage from "@/pages/explorer/items/my-files";

jest.mock("@/hooks/useDefaultRoute", () => ({
  useDefaultRoute: jest.fn(),
}));

jest.mock("@/features/layouts/components/explorer/ExplorerLayout", () => ({
  getGlobalExplorerLayout: jest.fn((page) => page),
}));

jest.mock("@/features/explorer/components/workspaces-explorer/WorkspacesExplorer", () => ({
  __esModule: true,
  default: jest.fn(() => <div>workspaces-explorer</div>),
}));

const mockedUseDefaultRoute = jest.mocked(useDefaultRoute);
const mockedGetGlobalExplorerLayout = jest.mocked(getGlobalExplorerLayout);
const mockedWorkspacesExplorer = jest.mocked(WorkspacesExplorer);

describe("MyFilesPage", () => {
  beforeEach(() => {
    mockedUseDefaultRoute.mockReset();
    mockedGetGlobalExplorerLayout.mockClear();
    mockedWorkspacesExplorer.mockClear();
  });

  it("keeps the my-files route shell on the default route and creator filter", () => {
    const html = renderToStaticMarkup(<MyFilesPage />);

    expect(html).toContain("workspaces-explorer");
    expect(mockedUseDefaultRoute).toHaveBeenCalledWith(DefaultRoute.MY_FILES);
    expect(mockedWorkspacesExplorer.mock.calls[0]?.[0]).toEqual({
      defaultFilters: { is_creator_me: true },
    });
  });

  it("keeps the global explorer layout host wired as the page getLayout", () => {
    const page = <div>page</div>;

    expect(MyFilesPage.getLayout?.(page)).toBe(page);
    expect(mockedGetGlobalExplorerLayout).toHaveBeenCalledWith(page);
  });
});
