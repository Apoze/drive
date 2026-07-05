import { ItemType, type Item } from "@/features/drivers/types";
import {
  getHeaderSearchDefaultFilters,
  isExplorerSearchShortcut,
} from "../searchEntrypointHelpers";

const buildItem = (overrides: Partial<Item> = {}): Item =>
  ({
    id: "item-1",
    title: "Workspace",
    filename: "Workspace",
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
    path: "/Workspace",
    abilities: {
      accesses_manage: false,
      accesses_view: true,
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
      partial_update: true,
      restore: false,
      retrieve: true,
      tree: true,
      update: true,
      upload_ended: false,
    },
    ...overrides,
  }) as Item;

describe("searchEntrypointHelpers", () => {
  it("matches only the intended search keyboard shortcuts", () => {
    expect(
      isExplorerSearchShortcut({
        key: "k",
        metaKey: true,
      }),
    ).toBe(true);
    expect(
      isExplorerSearchShortcut({
        key: "k",
        ctrlKey: true,
      }),
    ).toBe(true);
    expect(
      isExplorerSearchShortcut({
        key: "p",
        ctrlKey: true,
      }),
    ).toBe(false);
  });

  it("keeps the header default workspace filter scoped to minimal layout only", () => {
    const currentItem = buildItem({
      id: "folder-2",
      parents: [buildItem({ id: "workspace-1" })],
    });

    expect(
      getHeaderSearchDefaultFilters({
        currentItem,
        isMinimalLayout: true,
      }),
    ).toEqual({
      workspace: "workspace-1",
    });

    expect(
      getHeaderSearchDefaultFilters({
        currentItem,
        isMinimalLayout: false,
      }),
    ).toEqual({});
  });
});
