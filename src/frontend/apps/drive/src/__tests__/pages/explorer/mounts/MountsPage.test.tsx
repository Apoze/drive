import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/router";
import { useQuery } from "@tanstack/react-query";
import { getDriver } from "@/features/config/Config";
import {
  NavigationEventType,
  useGlobalExplorer,
} from "@/features/explorer/components/GlobalExplorerContext";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { getMountActionIds } from "@/features/mounts/utils/mountActionConfig";
import { MountsRootBrowseExplorer } from "@/features/mounts/components/MountsRootBrowseExplorer";

import MountsPage from "@/pages/explorer/mounts";

const renderedButtonProps: Array<{
  onClick?: () => void;
}> = [];

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => {
  const actual = jest.requireActual("@gouvfr-lasuite/cunningham-react");

  return {
    ...actual,
    Button: (props: { onClick?: () => void; children?: React.ReactNode }) => {
      renderedButtonProps.push(props);
      return <button>{props.children}</button>;
    },
  };
});

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock(
  "@/features/explorer/components/GlobalExplorerContext",
  () => ({
    useGlobalExplorer: jest.fn(),
    NavigationEventType: {
      ITEM: "item",
      KEYBOARD: "keyboard",
    },
  }),
);

jest.mock("@/hooks/useDefaultRoute", () => ({
  useDefaultRoute: jest.fn(),
}));

jest.mock("@/features/mounts/utils/mountActionConfig", () => ({
  getMountActionIds: jest.fn(),
}));

jest.mock("@/features/mounts/components/MountExplorerBreadcrumbs", () => ({
  MountExplorerBreadcrumbs: () => <div>mount-breadcrumbs</div>,
}));

jest.mock("@/features/mounts/components/MountsRootBrowseExplorer", () => ({
  MountsRootBrowseExplorer: jest.fn(() => <div>mounts-root-browse</div>),
}));

jest.mock("@/features/layouts/components/explorer/ExplorerLayout", () => ({
  getGlobalExplorerLayout: jest.fn((page) => page),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

const mockedUseRouter = jest.mocked(useRouter);
const mockedUseQuery = jest.mocked(useQuery);
const mockedGetDriver = jest.mocked(getDriver);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedUseDefaultRoute = jest.mocked(useDefaultRoute);
const mockedGetMountActionIds = jest.mocked(getMountActionIds);
const mockedMountsRootBrowseExplorer = jest.mocked(MountsRootBrowseExplorer);

const mountItem = {
  id: "mount-root:mount-1",
  title: "Shared Docs",
  filename: "Shared Docs",
  mountMeta: {
    mountId: "mount-1",
    normalizedPath: "/docs",
  },
} as never;

describe("MountsPage", () => {
  const push = jest.fn();
  const refetch = jest.fn();
  const openRightPanelForItem = jest.fn();
  const getMountsDiscovery = jest.fn();

  beforeEach(() => {
    renderedButtonProps.length = 0;
    push.mockReset();
    refetch.mockReset();
    openRightPanelForItem.mockReset();
    getMountsDiscovery.mockReset();
    mockedMountsRootBrowseExplorer.mockClear();
    mockedUseDefaultRoute.mockReset();
    mockedGetMountActionIds.mockReset();
    mockedUseRouter.mockReturnValue({
      push,
      query: {},
    } as never);
    mockedUseGlobalExplorer.mockReturnValue({
      selectedItems: [],
      openRightPanelForItem,
    } as never);
    mockedGetDriver.mockReturnValue({
      getMountsDiscovery,
    } as never);
    mockedUseQuery.mockImplementation(
      () =>
        ({
          data: [{ mount_id: "mount-1" }],
          isLoading: false,
          isError: false,
          refetch,
        }) as never,
    );
  });

  it("wires the mounts discovery query and default route", async () => {
    renderToStaticMarkup(<MountsPage />);

    expect(mockedUseDefaultRoute).toHaveBeenCalledWith(DefaultRoute.MOUNTS);
    const queryConfig = mockedUseQuery.mock.calls[0][0] as {
      queryKey: string[];
      refetchOnWindowFocus: boolean;
      queryFn: () => Promise<Array<{ mount_id: string }>>;
    };
    expect(queryConfig).toEqual(
      expect.objectContaining({
        queryKey: ["mounts", "discovery"],
        refetchOnWindowFocus: false,
      }),
    );

    getMountsDiscovery.mockResolvedValue([{ mount_id: "mount-1" }]);
    await expect(queryConfig.queryFn()).resolves.toEqual([{ mount_id: "mount-1" }]);
    expect(getMountsDiscovery).toHaveBeenCalledWith();
  });

  it("wires selection browse, context menu actions and item navigation coherently", () => {
    mockedUseGlobalExplorer.mockReturnValue({
      selectedItems: [mountItem],
      openRightPanelForItem,
    } as never);
    mockedGetMountActionIds.mockReturnValue(["browse", "view_info"]);

    renderToStaticMarkup(<MountsPage />);

    const props = mockedMountsRootBrowseExplorer.mock.calls[0][0] as {
      selectionBarActions: React.ReactNode;
      getContextMenuItems: (item: unknown) => Array<{ callback?: () => void }>;
      onNavigate: (event: unknown) => void;
    };
    renderToStaticMarkup(props.selectionBarActions as React.ReactElement);
    renderedButtonProps[0]?.onClick?.();

    expect(push).toHaveBeenCalledWith({
      pathname: "/explorer/mounts/[mount_id]",
      query: {
        mount_id: "mount-1",
        path: "/docs",
      },
    });

    const menuItems = props.getContextMenuItems(mountItem);
    menuItems[0].callback?.();
    menuItems[1].callback?.();

    expect(push).toHaveBeenCalledTimes(2);
    expect(openRightPanelForItem).toHaveBeenCalledWith(mountItem);

    props.onNavigate({
      type: NavigationEventType.ITEM,
      item: mountItem,
    } as never);
    props.onNavigate({
      type: "keyboard",
      item: mountItem,
    } as never);

    expect(push).toHaveBeenCalledTimes(3);
  });

  it("hides the selection action when the current selection cannot browse", () => {
    mockedUseGlobalExplorer.mockReturnValue({
      selectedItems: [mountItem],
      openRightPanelForItem,
    } as never);
    mockedGetMountActionIds.mockReturnValue(["view_info"]);

    renderToStaticMarkup(<MountsPage />);

    const props = mockedMountsRootBrowseExplorer.mock.calls[0][0] as {
      selectionBarActions: React.ReactNode;
    };
    const html = renderToStaticMarkup(props.selectionBarActions as React.ReactElement);

    expect(html).toBe("");
  });
});
