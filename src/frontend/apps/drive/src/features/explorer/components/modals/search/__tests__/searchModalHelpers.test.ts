import { ItemType, type Item } from "@/features/drivers/types";
import {
  activateExplorerSearchItem,
  buildExplorerSearchQuery,
  shouldClearExplorerSearchResults,
} from "../searchModalHelpers";

const buildItem = (overrides: Partial<Item> = {}): Item => ({
  id: "item-1",
  title: "Report",
  filename: "Report.txt",
  creator: {
    id: "user-1",
    full_name: "Jane Doe",
    short_name: "JD",
  },
  type: ItemType.FILE,
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: null,
  computed_link_role: null,
  upload_state: "ready",
  updated_at: new Date("2026-03-22T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-22T00:00:00Z"),
  path: "/Report.txt",
  abilities: {
    accesses_manage: false,
    accesses_view: true,
    children_create: false,
    children_list: false,
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
    tree: false,
    update: true,
    upload_ended: false,
  },
  ...overrides,
});

describe("searchModalHelpers", () => {
  it("builds and clears the search query consistently", () => {
    expect(shouldClearExplorerSearchResults("", {})).toBe(true);
    expect(
      shouldClearExplorerSearchResults("", {
        workspace: "workspace-1",
      }),
    ).toBe(false);
    expect(
      buildExplorerSearchQuery(
        {
          workspace: "workspace-1",
          scope: "deleted" as never,
        },
        "report",
      ),
    ).toEqual({
      workspace: "workspace-1",
      scope: "deleted",
      title: "report",
    });
  });

  it("navigates and closes for non-deleted folders", () => {
    const onNavigate = jest.fn();
    const onClose = jest.fn();
    const openSinglePreview = jest.fn();
    const onTrashFolderBlocked = jest.fn();
    const item = buildItem({
      type: ItemType.FOLDER,
      filename: "Workspace",
      path: "/Workspace",
    });

    activateExplorerSearchItem({
      item,
      onNavigate,
      openSinglePreview,
      onClose,
      onTrashFolderBlocked,
    });

    expect(onNavigate).toHaveBeenCalledWith({
      item,
      type: "item",
    });
    expect(onClose).toHaveBeenCalled();
    expect(openSinglePreview).not.toHaveBeenCalled();
    expect(onTrashFolderBlocked).not.toHaveBeenCalled();
  });

  it("blocks navigation for deleted folders and previews files", () => {
    const onNavigate = jest.fn();
    const onClose = jest.fn();
    const openSinglePreview = jest.fn();
    const onTrashFolderBlocked = jest.fn();
    const onFileActivated = jest.fn();

    activateExplorerSearchItem({
      item: buildItem({
        type: ItemType.FOLDER,
        deleted_at: new Date("2026-03-22T00:00:00Z"),
      }),
      onNavigate,
      openSinglePreview,
      onClose,
      onTrashFolderBlocked,
    });

    expect(onTrashFolderBlocked).toHaveBeenCalled();
    expect(onNavigate).not.toHaveBeenCalled();

    const fileItem = buildItem();
    activateExplorerSearchItem({
      item: fileItem,
      onNavigate,
      openSinglePreview,
      onClose,
      onTrashFolderBlocked,
      onFileActivated,
    });

    expect(openSinglePreview).toHaveBeenCalledWith(fileItem);
    expect(onFileActivated).toHaveBeenCalled();
  });
});
