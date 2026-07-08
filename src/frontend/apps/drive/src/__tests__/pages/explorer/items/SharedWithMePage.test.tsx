import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import WorkspacesExplorer from "@/features/explorer/components/workspaces-explorer/WorkspacesExplorer";
import SharedPage from "@/pages/explorer/items/shared-with-me";

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

describe("SharedPage", () => {
  beforeEach(() => {
    mockedUseDefaultRoute.mockReset();
    mockedGetGlobalExplorerLayout.mockClear();
    mockedWorkspacesExplorer.mockClear();
  });

  it("keeps the shared-with-me route shell on the shared filter and default route", () => {
    const html = renderToStaticMarkup(<SharedPage />);

    expect(html).toContain("workspaces-explorer");
    expect(mockedUseDefaultRoute).toHaveBeenCalledWith(DefaultRoute.SHARED_WITH_ME);
    expect(mockedWorkspacesExplorer.mock.calls[0]?.[0]).toEqual({
      defaultFilters: { is_creator_me: false },
      viewConfigKey: DefaultRoute.SHARED_WITH_ME,
    });
  });

  it("keeps the global explorer layout host wired as the page getLayout", () => {
    const page = <div>page</div>;

    expect(SharedPage.getLayout?.(page)).toBe(page);
    expect(mockedGetGlobalExplorerLayout).toHaveBeenCalledWith(page);
  });
});
