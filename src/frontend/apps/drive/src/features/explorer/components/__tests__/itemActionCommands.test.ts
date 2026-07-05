import { DefaultRoute } from "@/utils/defaultRoutes";
import { Item, ItemType } from "@/features/drivers/types";
import {
  applyFavoriteTreeSync,
  canDeleteItems,
  getDeleteItemIds,
  handleFavoriteCommand,
} from "../itemActionCommands";
import { itemToTreeItem } from "../GlobalExplorerContext";

jest.mock("../GlobalExplorerContext", () => ({
  itemToTreeItem: jest.fn(),
}));

const mockedItemToTreeItem = jest.mocked(itemToTreeItem);

const buildItem = (overrides: Partial<Item> = {}): Item => ({
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
  path: "/Folder",
  abilities: {
    accesses_manage: false,
    accesses_view: false,
    children_create: true,
    children_list: true,
    destroy: true,
    favorite: false,
    invite_owner: false,
    link_configuration: false,
    media_auth: false,
    move: true,
    link_select_options: {
      restricted: null,
      authenticated: null,
      public: null,
    },
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: true,
    update: true,
    upload_ended: false,
  },
  ...overrides,
});

describe("itemActionCommands", () => {
  beforeEach(() => {
    mockedItemToTreeItem.mockReset();
    mockedItemToTreeItem.mockReturnValue({ id: "favorite-tree-item" } as never);
  });

  it("accepts delete only when the whole selection is destroyable", () => {
    expect(canDeleteItems([])).toBe(false);
    expect(
      canDeleteItems([
        buildItem(),
        buildItem({ id: "item-2", abilities: { ...buildItem().abilities, destroy: true } }),
      ]),
    ).toBe(true);
    expect(
      canDeleteItems([
        buildItem(),
        buildItem({ id: "item-2", abilities: { ...buildItem().abilities, destroy: false } }),
      ]),
    ).toBe(false);
  });

  it("maps selection items to delete ids", () => {
    expect(getDeleteItemIds([buildItem(), buildItem({ id: "item-2" })])).toEqual([
      "item-1",
      "item-2",
    ]);
  });

  it("syncs favorite tree only for folders", () => {
    const addFavoriteChild = jest.fn();

    applyFavoriteTreeSync({
      item: buildItem(),
      addFavoriteChild,
    });

    expect(mockedItemToTreeItem).toHaveBeenCalledWith(
      expect.objectContaining({ id: "item-1" }),
      DefaultRoute.FAVORITES,
      true,
    );
    expect(addFavoriteChild).toHaveBeenCalledWith({ id: "favorite-tree-item" });

    mockedItemToTreeItem.mockClear();
    addFavoriteChild.mockClear();

    applyFavoriteTreeSync({
      item: buildItem({ type: ItemType.FILE }),
      addFavoriteChild,
    });

    expect(mockedItemToTreeItem).not.toHaveBeenCalled();
    expect(addFavoriteChild).not.toHaveBeenCalled();
  });

  it("runs create favorite and applies the shared tree sync on success", async () => {
    const addFavoriteChild = jest.fn();
    const createFavoriteItem = jest.fn(
      async (_itemId: string, options?: { onSuccess?: () => void }) => {
        options?.onSuccess?.();
      },
    );

    await handleFavoriteCommand({
      createFavoriteItem,
      effectiveItemId: "item-1",
      item: buildItem(),
      addFavoriteChild,
    });

    expect(createFavoriteItem).toHaveBeenCalledWith(
      "item-1",
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    expect(addFavoriteChild).toHaveBeenCalledWith({ id: "favorite-tree-item" });
  });
});
