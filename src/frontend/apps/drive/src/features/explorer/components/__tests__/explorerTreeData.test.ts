import { ItemType } from "@/features/drivers/types";
import {
  generateTreeId,
  getOriginalIdFromTreeId,
  itemToTreeItem,
  itemsToTreeItems,
} from "../explorerTreeData";

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
    numchild_folder: 0,
    children: [],
    abilities: {
      children_create: true,
      move: true,
    },
    ...overrides,
  }) as never;

describe("explorerTreeData", () => {
  it("keeps favorite tree ids path-based and recovers original ids", () => {
    expect(generateTreeId("item-1")).toBe("item-1");
    expect(generateTreeId("item-1", "favorites", true)).toBe("favorites::item-1");
    expect(getOriginalIdFromTreeId("favorites::folder-1::item-1")).toBe("item-1");
  });

  it("maps an item tree recursively while preserving original ids", () => {
    const treeItem = itemToTreeItem(
      buildItem({
        id: "parent-1",
        children: [
          buildItem({
            id: "child-1",
            title: "Child",
            filename: "Child",
          }),
        ],
      }),
      "favorites",
      true,
    );

    expect(treeItem).toMatchObject({
      id: "favorites::parent-1",
      originalId: "parent-1",
      parentId: "favorites",
      title: "Folder",
      childrenCount: 0,
    });
    expect(treeItem.children?.[0]).toMatchObject({
      id: "favorites::parent-1::child-1",
      originalId: "child-1",
      parentId: "favorites::parent-1",
    });
  });

  it("maps a list of items through the canonical tree item builder", () => {
    expect(
      itemsToTreeItems([
        buildItem({ id: "item-1" }),
        buildItem({ id: "item-2" }),
      ], "parent-1"),
    ).toEqual([
      expect.objectContaining({
        id: "item-1",
        parentId: "parent-1",
      }),
      expect.objectContaining({
        id: "item-2",
        parentId: "parent-1",
      }),
    ]);
  });
});
