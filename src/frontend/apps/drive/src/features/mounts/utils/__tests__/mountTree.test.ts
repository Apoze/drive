import { ItemType } from "@/features/drivers/types";
import { DefaultRoute } from "@/utils/defaultRoutes";
import {
  buildMountsTreeRoot,
  discoveryToMountTreeItem,
  entryToMountTreeItem,
  getMountTreeParentNodeId,
  getMountRouteTreeSelectionId,
  getMountTreeNodeId,
  parseMountTreeNodeId,
} from "../mountTree";

describe("mountTree", () => {
  it("builds the mounts shell root as a simple node", () => {
    expect(buildMountsTreeRoot("Mounts", 2)).toMatchObject({
      id: DefaultRoute.MOUNTS,
      label: "Mounts",
      childrenCount: 2,
    });
  });

  it("round-trips mount tree node ids", () => {
    expect(parseMountTreeNodeId(getMountTreeNodeId("alpha", "/"))).toEqual({
      mountId: "alpha",
      normalizedPath: "/",
    });

    expect(
      parseMountTreeNodeId(getMountTreeNodeId("alpha", "/projects/nested")),
    ).toEqual({
      mountId: "alpha",
      normalizedPath: "/projects/nested",
    });

    expect(getMountTreeParentNodeId("alpha", "/projects/nested")).toBe(
      "mount-entry:alpha:/projects",
    );
    expect(getMountTreeParentNodeId("alpha", "/projects")).toBe(
      "mount-root:alpha",
    );
  });

  it("maps a discovery root to a lazy-loadable tree folder", () => {
    const treeItem = discoveryToMountTreeItem({
      mount_id: "alpha",
      display_name: "Finance",
      provider: "smb",
      capabilities: {},
    });

    expect(treeItem).toMatchObject({
      id: "mount-root:alpha",
      parentId: DefaultRoute.MOUNTS,
      type: ItemType.FOLDER,
      childrenCount: 1,
    });
  });

  it("maps a browseable mount folder entry to a lazy-loadable tree node", () => {
    const treeItem = entryToMountTreeItem({
      mountId: "alpha",
      mountTitle: "Finance",
      provider: "smb",
      parentId: "mount-root:alpha",
      entry: {
        mount_id: "alpha",
        normalized_path: "/projects",
        entry_type: "folder",
        name: "projects",
        abilities: {
          children_list: true,
          create_folder: true,
          move: true,
          rename: true,
          destroy: true,
          upload: true,
          duplicate: false,
          download: false,
          preview: false,
          wopi: false,
          share_link_create: false,
        },
      },
    });

    expect(treeItem).toMatchObject({
      id: "mount-entry:alpha:/projects",
      parentId: "mount-root:alpha",
      type: ItemType.FOLDER,
      childrenCount: 1,
    });
  });

  it("selects the current parent folder for preview and wopi routes", () => {
    expect(
      getMountRouteTreeSelectionId({
        pathname: "/explorer/mounts/[mount_id]/preview",
        mountId: "alpha",
        path: "/projects/readme.txt",
      }),
    ).toBe("mount-entry:alpha:/projects");

    expect(
      getMountRouteTreeSelectionId({
        pathname: "/explorer/mounts/[mount_id]/wopi",
        mountId: "alpha",
        path: "/report.docx",
      }),
    ).toBe("mount-root:alpha");
  });
});
