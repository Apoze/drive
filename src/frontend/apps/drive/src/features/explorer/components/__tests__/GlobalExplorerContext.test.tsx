import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/Auth";
import { useFirstLevelItems } from "../../hooks/useQueries";
import {
  GlobalExplorerProvider,
  useGlobalExplorer,
} from "../GlobalExplorerContext";
import { DefaultRoute } from "@/utils/defaultRoutes";

const renderedTreeProviderProps: Array<{
  initialNodeId?: string;
  onLoadChildren?: (treeId: string, page: number) => Promise<unknown>;
}> = [];

let capturedContext: ReturnType<typeof useGlobalExplorer> | undefined;

const driver = {
  getItem: jest.fn(),
  getMountsDiscovery: jest.fn(),
  getFavoriteItems: jest.fn(),
  getChildren: jest.fn(),
  browseMount: jest.fn(),
};

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

jest.mock("../../hooks/useQueries", () => ({
  useFirstLevelItems: jest.fn(),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: () => driver,
}));

jest.mock("@/features/explorer/hooks/useUpload", () => ({
  useUploadZone: () => ({
    dropZone: {
      getInputProps: (props: Record<string, unknown>) => props,
    },
  }),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  TreeProvider: (props: {
    children?: React.ReactNode;
    initialNodeId?: string;
    onLoadChildren?: (treeId: string, page: number) => Promise<unknown>;
  }) => {
    renderedTreeProviderProps.push(props);
    return <div>{props.children}</div>;
  },
  TreeViewNodeTypeEnum: {
    NODE: "node",
    SIMPLE_NODE: "simple-node",
  },
  useTreeContext: () => ({
    treeData: {
      resetTree: jest.fn(),
    },
  }),
}));

jest.mock("@/features/explorer/components/ExplorerDndProvider", () => ({
  ExplorerDndProvider: ({ children }: { children?: React.ReactNode }) => (
    <div>dnd-provider{children}</div>
  ),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  Toaster: () => <div>toaster</div>,
}));

jest.mock("@/features/ui/components/spinner/SpinnerPage", () => ({
  SpinnerPage: () => <div>spinner-page</div>,
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedUseAuth = jest.mocked(useAuth);
const mockedUseFirstLevelItems = jest.mocked(useFirstLevelItems);

const buildItem = (id: string, title: string) =>
  ({
    id,
    title,
    filename: title,
    creator: {
      id: "user-1",
      full_name: "Jane Doe",
      short_name: "JD",
    },
    type: "folder",
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-22T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-22T00:00:00Z"),
    path: `${id}.path`,
    numchild_folder: 0,
    abilities: {
      children_create: true,
      move: true,
    },
  }) as never;

describe("GlobalExplorerProvider", () => {
  beforeEach(() => {
    renderedTreeProviderProps.length = 0;
    capturedContext = undefined;
    driver.getItem.mockReset();
    driver.getMountsDiscovery.mockReset();
    driver.getFavoriteItems.mockReset();
    driver.getChildren.mockReset();
    driver.browseMount.mockReset();
    mockedUseQuery.mockReturnValue({
      data: buildItem("folder-1", "Folder"),
    } as never);
    mockedUseAuth.mockReturnValue({
      user: {
        id: "user-1",
        main_workspace: buildItem("workspace-main", "Main workspace"),
      },
    } as never);
    mockedUseFirstLevelItems.mockReturnValue({
      data: [buildItem("workspace-main", "Main workspace")],
    } as never);
  });

  it("wires the canonical provider hosts, hidden import inputs and explicit context APIs", () => {
    const Harness = () => {
      capturedContext = useGlobalExplorer();
      return <div>provider-child</div>;
    };

    const html = renderToStaticMarkup(
      <GlobalExplorerProvider
        displayMode="app"
        itemId="folder-1"
        onNavigate={jest.fn()}
      >
        <Harness />
      </GlobalExplorerProvider>,
    );

    expect(renderedTreeProviderProps[0]?.initialNodeId).toBe("folder-1");
    expect(html).toContain("dnd-provider");
    expect(html).toContain("toaster");
    expect(html).toContain("id=\"import-folders\"");
    expect(html).toContain("id=\"import-files\"");
    expect(capturedContext).toMatchObject({
      displayMode: "app",
      itemId: "folder-1",
      mainWorkspace: expect.objectContaining({
        id: "workspace-main",
      }),
    });
    expect(capturedContext?.openPreview).toEqual(expect.any(Function));
    expect(capturedContext?.openRightPanelForItem).toEqual(expect.any(Function));
    expect(capturedContext?.refreshMobileNodes).toEqual(expect.any(Function));
  });

  it("keeps favorites and mounts branches on the TreeProvider runtime contract", async () => {
    driver.getFavoriteItems.mockResolvedValue({
      children: [buildItem("favorite-folder", "Favorite folder")],
      pagination: {
        currentPage: 1,
        totalCount: 1,
        hasMore: false,
      },
    });
    driver.getMountsDiscovery.mockResolvedValue([
      {
        mount_id: "mount-1",
        title: "Mount 1",
        provider: "smb",
      },
    ]);

    renderToStaticMarkup(
      <GlobalExplorerProvider
        displayMode="app"
        itemId="folder-1"
        onNavigate={jest.fn()}
      >
        <div>child</div>
      </GlobalExplorerProvider>,
    );

    const favoriteChildren = (await renderedTreeProviderProps[0]?.onLoadChildren?.(
      DefaultRoute.FAVORITES,
      1,
    )) as {
      children: Array<{ id: string }>;
    };
    const mountsChildren = (await renderedTreeProviderProps[0]?.onLoadChildren?.(
      DefaultRoute.MOUNTS,
      1,
    )) as {
      children: Array<{ id: string }>;
    };

    expect(favoriteChildren.children[0]?.id).toBe(
      `${DefaultRoute.FAVORITES}::favorite-folder`,
    );
    expect(mountsChildren.children[0]?.id).toContain("mount-root:mount-1");
  });

  it("rebases the tree runtime on the current route item id instead of the first mounted folder", () => {
    renderToStaticMarkup(
      <GlobalExplorerProvider
        displayMode="app"
        itemId="folder-1"
        onNavigate={jest.fn()}
      >
        <div>first-render</div>
      </GlobalExplorerProvider>,
    );

    mockedUseQuery.mockReturnValue({
      data: buildItem("folder-2", "Folder 2"),
    } as never);

    renderToStaticMarkup(
      <GlobalExplorerProvider
        displayMode="app"
        itemId="folder-2"
        onNavigate={jest.fn()}
      >
        <div>second-render</div>
      </GlobalExplorerProvider>,
    );

    expect(renderedTreeProviderProps[0]?.initialNodeId).toBe("folder-1");
    expect(renderedTreeProviderProps[1]?.initialNodeId).toBe("folder-2");
  });
});
