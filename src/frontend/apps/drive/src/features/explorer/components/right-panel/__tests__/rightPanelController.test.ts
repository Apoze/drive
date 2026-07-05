import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  type Item,
} from "@/features/drivers/types";
import { createRightPanelController } from "../rightPanelController";

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
  upload_state: ItemUploadState.READY,
  updated_at: new Date("2026-03-22T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-22T00:00:00Z"),
  path: "/Report.txt",
  mimetype: "text/plain",
  link_reach: LinkReach.RESTRICTED,
  link_role: LinkRole.READER,
  abilities: {
    accesses_manage: false,
    accesses_view: true,
    children_create: false,
    children_list: false,
    destroy: false,
    favorite: false,
    invite_owner: false,
    link_configuration: false,
    media_auth: false,
    move: false,
    link_select_options: {
      [LinkReach.RESTRICTED]: null,
      [LinkReach.AUTHENTICATED]: null,
      [LinkReach.PUBLIC]: null,
    },
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: false,
    update: false,
    upload_ended: false,
  },
  ...overrides,
});

describe("rightPanelController", () => {
  it("centralizes open, close, replace and conditional clear operations for the right panel", () => {
    const setRightPanelForcedItem = jest.fn();
    const setRightPanelOpen = jest.fn();
    const currentItem = buildItem();
    const nextItem = buildItem({ title: "Report v2" });
    const controller = createRightPanelController({
      rightPanelForcedItem: currentItem,
      setRightPanelForcedItem,
      rightPanelOpen: true,
      setRightPanelOpen,
    });

    controller.openRightPanelForItem(currentItem);
    controller.replaceRightPanelItemIfCurrent(currentItem.id, nextItem);
    controller.closeRightPanelIfCurrent("other-item");
    controller.closeRightPanelIfIncluded([{ id: currentItem.id }]);
    controller.closeRightPanel();
    controller.clearRightPanelItem();

    expect(setRightPanelForcedItem).toHaveBeenNthCalledWith(1, currentItem);
    expect(setRightPanelOpen).toHaveBeenNthCalledWith(1, true);
    expect(setRightPanelForcedItem).toHaveBeenNthCalledWith(2, nextItem);
    expect(setRightPanelForcedItem).toHaveBeenNthCalledWith(3, undefined);
    expect(setRightPanelOpen).toHaveBeenNthCalledWith(2, false);
    expect(setRightPanelOpen).toHaveBeenNthCalledWith(3, false);
    expect(setRightPanelForcedItem).toHaveBeenNthCalledWith(4, undefined);
  });
});
