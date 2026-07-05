import { DefaultRoute } from "@/utils/defaultRoutes";
import { ItemType } from "@/features/drivers/types";
import { TreeViewNodeTypeEnum } from "@gouvfr-lasuite/ui-kit";
import { canDrop, snapToTopLeft } from "../explorerDndRuntime";

jest.mock("@dnd-kit/utilities", () => ({
  getEventCoordinates: () => ({
    x: 50,
    y: 80,
  }),
}));

const buildItem = (overrides: Record<string, unknown> = {}) =>
  ({
    id: "item-1",
    title: "Folder",
    filename: "Folder",
    creator: {
      id: "user-1",
      full_name: "Jane Doe",
      short_name: "JD",
    },
    type: ItemType.FOLDER,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-22T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-22T00:00:00Z"),
    path: "workspace.folder",
    abilities: {
      children_create: true,
      move: true,
    },
    ...overrides,
  }) as never;

describe("explorerDndRuntime", () => {
  it("keeps the top-left snap modifier aligned with the pointer offset", () => {
    expect(
      snapToTopLeft({
        activatorEvent: {
          clientX: 50,
          clientY: 80,
        } as never,
        draggingNodeRect: {
          left: 20,
          top: 40,
        } as never,
        transform: {
          x: 5,
          y: 10,
          scaleX: 1,
          scaleY: 1,
        },
        active: {} as never,
        over: null,
        activeNodeRect: null,
        containerNodeRect: null,
        overlayNodeRect: null,
        scrollableAncestors: [],
        scrollableAncestorRects: [],
        windowRect: null,
      }),
    ).toEqual({
      x: 30,
      y: 45,
      scaleX: 1,
      scaleY: 1,
    });
  });

  it("accepts favorites drops but rejects self, descendants and direct-parent drops", () => {
    const activeItem = buildItem({
      id: "favorites::item-1",
      path: "workspace.folder.item-1",
    });

    expect(
      canDrop(
        activeItem,
        buildItem({
          id: DefaultRoute.FAVORITES,
          nodeType: TreeViewNodeTypeEnum.NODE,
          path: DefaultRoute.FAVORITES,
        }),
      ),
    ).toBe(true);

    expect(
      canDrop(
        activeItem,
        buildItem({
          id: "item-1",
          nodeType: TreeViewNodeTypeEnum.NODE,
          path: "workspace.folder.item-1",
        }),
      ),
    ).toBe(false);

    expect(
      canDrop(
        activeItem,
        buildItem({
          id: "child-folder",
          nodeType: TreeViewNodeTypeEnum.NODE,
          path: "workspace.folder.item-1.child",
        }),
      ),
    ).toBe(false);

    expect(
      canDrop(
        activeItem,
        buildItem({
          id: "folder",
          nodeType: TreeViewNodeTypeEnum.NODE,
          path: "workspace.folder",
        }),
      ),
    ).toBe(false);
  });
});
