import {
  buildExplorerLayoutNavigateTarget,
  getExplorerTreeDefaultRoutes,
  getExplorerTreeSelectedNodeId,
  resolveExplorerPanelsLayoutState,
  resolveExplorerTreeMoveDecision,
} from "../explorerShellHelpers";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { getMountRouteTreeSelectionId } from "@/features/mounts/utils/mountTree";

describe("explorerShellHelpers", () => {
  it("keeps only the minimal query and prefers originalId for explorer navigation", () => {
    expect(
      buildExplorerLayoutNavigateTarget({
        item: {
          id: "item-1",
          originalId: "favorite-1",
        } as never,
        minimal: "true",
      }),
    ).toEqual({
      id: "favorite-1",
      pathname: "/explorer/items/[id]",
      query: {
        id: "favorite-1",
        minimal: "true",
      },
    });
  });

  it("derives the shell panel mode from user presence and minimal layout", () => {
    expect(
      resolveExplorerPanelsLayoutState({
        hasUser: true,
        isMinimalLayout: false,
      }),
    ).toEqual({
      showExplorerTree: true,
      hideLeftPanelOnDesktop: false,
    });

    expect(
      resolveExplorerPanelsLayoutState({
        hasUser: false,
        isMinimalLayout: false,
      }),
    ).toEqual({
      showExplorerTree: false,
      hideLeftPanelOnDesktop: true,
    });
  });

  it("resolves tree selection for mount routes, default routes and item routes", () => {
    expect(
      getExplorerTreeSelectedNodeId({
        pathname: "/explorer/mounts/[mount_id]",
        mountId: "mount-1",
        path: "/folder",
        itemId: "item-1",
      }),
    ).toBe(
      getMountRouteTreeSelectionId({
        pathname: "/explorer/mounts/[mount_id]",
        mountId: "mount-1",
        path: "/folder",
      }),
    );

    expect(
      getExplorerTreeSelectedNodeId({
        pathname: "/explorer/items/recent",
        itemId: "item-1",
      }),
    ).toBe(DefaultRoute.RECENT);

    expect(
      getExplorerTreeSelectedNodeId({
        pathname: "/explorer/items/item-1",
        itemId: "item-1",
      }),
    ).toBe("item-1");
  });

  it("keeps the default tree navigation filtered away from favorites and mounts", () => {
    const routeIds = getExplorerTreeDefaultRoutes().map((route) => route.id);

    expect(routeIds).not.toContain(DefaultRoute.FAVORITES);
    expect(routeIds).not.toContain(DefaultRoute.MOUNTS);
    expect(routeIds).toContain(DefaultRoute.MY_FILES);
    expect(routeIds).toContain(DefaultRoute.RECENT);
  });

  it("separates direct moves from cross-workspace confirmation moves", () => {
    const sourceItem = {
      id: "file-1",
      title: "Report",
      path: "workspace-1.folder.report",
    } as never;
    const sameWorkspaceParent = {
      id: "parent-2",
      title: "Folder",
      path: "workspace-1.folder-2",
    } as never;
    const oldParent = {
      id: "parent-1",
      title: "Folder",
      path: "workspace-1.folder-1",
    } as never;

    expect(
      resolveExplorerTreeMoveDecision({
        sourceItem,
        parent: sameWorkspaceParent,
        oldParent,
      }),
    ).toEqual({
      kind: "direct",
    });

    expect(
      resolveExplorerTreeMoveDecision({
        sourceItem,
        parent: {
          id: "workspace-2-parent",
          title: "Other workspace",
          path: "workspace-2.folder",
        } as never,
        oldParent,
      }),
    ).toEqual({
      kind: "confirm",
      sourceItem: oldParent,
      targetItem: {
        id: "workspace-2-parent",
        title: "Other workspace",
        path: "workspace-2.folder",
      },
    });
  });
});
