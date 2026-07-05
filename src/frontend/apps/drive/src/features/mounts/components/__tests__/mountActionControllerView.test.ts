import { ItemType } from "@/features/drivers/types";
import type { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import {
  getMountContextMenuActionIds,
  getMountSelectionBarActionIds,
} from "../mountActionControllerView";

jest.mock("@/features/mounts/utils/mountActionConfig", () => ({
  getMountActionIds: jest.fn(),
}));

const { getMountActionIds } = jest.requireMock(
  "@/features/mounts/utils/mountActionConfig",
) as {
  getMountActionIds: jest.Mock;
};

const buildItem = (overrides: Partial<MountExplorerItem> = {}) =>
  ({
    id: "mount-entry:mount-1:/docs/report.txt",
    title: "report.txt",
    filename: "report.txt",
    creator: {
      id: "mount",
      full_name: "Mount",
      short_name: "MT",
    },
    type: ItemType.FILE,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-31T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-31T00:00:00Z"),
    path: "/docs/report.txt",
    abilities: {},
    mountMeta: {
      mountId: "mount-1",
      normalizedPath: "/docs/report.txt",
      entryType: "file",
      mountTitle: "Shared Docs",
      provider: "localfs",
      abilities: {},
    },
    ...overrides,
  }) as MountExplorerItem;

describe("getMountSelectionBarActionIds", () => {
  beforeEach(() => {
    getMountActionIds.mockReset();
  });

  it("returns nothing for an empty selection", () => {
    expect(getMountSelectionBarActionIds([])).toEqual([]);
    expect(getMountActionIds).not.toHaveBeenCalled();
  });

  it("keeps the fixed multi-selection action ids", () => {
    expect(getMountSelectionBarActionIds([buildItem(), buildItem({ id: "other" })])).toEqual([
      "delete",
      "move",
    ]);
    expect(getMountActionIds).not.toHaveBeenCalled();
  });

  it("filters single-item actions to the allowed selection-bar ids", () => {
    getMountActionIds.mockReturnValue([
      "preview",
      "share",
      "download",
      "move",
      "rename",
      "delete",
      "view_info",
      "separator",
    ]);

    expect(getMountSelectionBarActionIds([buildItem()])).toEqual([
      "preview",
      "share",
      "download",
      "rename",
      "move",
      "delete",
    ]);
  });
});

describe("getMountContextMenuActionIds", () => {
  beforeEach(() => {
    getMountActionIds.mockReset();
  });

  it("adds separator and view_info when primary actions exist", () => {
    getMountActionIds.mockReturnValue([
      "browse",
      "share",
      "rename",
      "move",
      "view_info",
      "delete",
    ]);

    expect(
      getMountContextMenuActionIds(
        buildItem({
          type: ItemType.FOLDER,
          mountMeta: {
            ...buildItem().mountMeta,
            entryType: "folder",
          },
        }),
      ),
    ).toEqual([
      "browse",
      "share",
      "rename",
      "move",
      "separator",
      "view_info",
      "separator",
      "delete",
    ]);
  });

  it("keeps only view_info when no primary action is available", () => {
    getMountActionIds.mockReturnValue(["view_info"]);

    expect(getMountContextMenuActionIds(buildItem())).toEqual(["view_info"]);
  });
});
