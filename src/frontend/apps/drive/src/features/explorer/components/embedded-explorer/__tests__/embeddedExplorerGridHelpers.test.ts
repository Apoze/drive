import { ItemType } from "@/features/drivers/types";
import { canMountItemReceiveDrop } from "@/features/mounts/utils/mountDnd";
import { isEmbeddedExplorerGridDropDisabled } from "../embeddedExplorerGridHelpers";

jest.mock("@/features/mounts/utils/mountDnd", () => ({
  canMountItemReceiveDrop: jest.fn(),
}));

const mockedCanMountItemReceiveDrop = jest.mocked(canMountItemReceiveDrop);

const buildItem = (overrides: Record<string, unknown> = {}) =>
  ({
    id: "item-1",
    title: "Folder",
    filename: "Folder",
    type: ItemType.FOLDER,
    creator: {
      id: "user-1",
      full_name: "Jane Doe",
      short_name: "JD",
    },
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-23T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-23T00:00:00Z"),
    path: "/Folder",
    abilities: {
      children_create: false,
      move: true,
    },
    ...overrides,
  }) as never;

describe("embeddedExplorerGridHelpers", () => {
  beforeEach(() => {
    mockedCanMountItemReceiveDrop.mockReset();
  });

  it("disables drop for selected rows, non-folders, and folders without a supported target capability", () => {
    mockedCanMountItemReceiveDrop.mockReturnValue(false);

    expect(
      isEmbeddedExplorerGridDropDisabled({
        item: buildItem(),
        isSelected: true,
      }),
    ).toBe(true);

    expect(
      isEmbeddedExplorerGridDropDisabled({
        item: buildItem({ type: ItemType.FILE }),
        isSelected: false,
      }),
    ).toBe(true);

    expect(
      isEmbeddedExplorerGridDropDisabled({
        item: buildItem(),
        isSelected: false,
      }),
    ).toBe(true);

    expect(
      isEmbeddedExplorerGridDropDisabled({
        item: buildItem({
          abilities: {
            children_create: true,
          },
        }),
        isSelected: false,
      }),
    ).toBe(false);

    mockedCanMountItemReceiveDrop.mockReturnValue(true);
    expect(
      isEmbeddedExplorerGridDropDisabled({
        item: buildItem(),
        isSelected: false,
      }),
    ).toBe(false);
  });
});
