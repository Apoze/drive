import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MountBrowseExplorer } from "@/features/mounts/components/MountBrowseExplorer";

jest.mock("@/features/mounts/components/MountBrowseExplorer", () => ({
  MountBrowseExplorer: jest.fn(() => <div>mount-browse-explorer</div>),
}));

jest.mock("@/features/layouts/components/explorer/ExplorerLayout", () => ({
  getGlobalExplorerLayout: jest.fn((page) => page),
}));

const mockedMountBrowseExplorer = jest.mocked(MountBrowseExplorer);

describe("mount route thinness", () => {
  let MountBrowsePage: React.ComponentType;

  beforeAll(async () => {
    MountBrowsePage = (
      await import("@/pages/explorer/mounts/[mount_id]")
    ).default;
  });

  beforeEach(() => {
    mockedMountBrowseExplorer.mockClear();
  });

  it("delegates the route rendering to the feature controller", () => {
    renderToStaticMarkup(<MountBrowsePage />);

    expect(mockedMountBrowseExplorer).toHaveBeenCalledTimes(1);
  });
});
