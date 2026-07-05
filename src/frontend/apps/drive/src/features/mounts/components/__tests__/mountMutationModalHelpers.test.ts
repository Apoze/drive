import { ItemType } from "@/features/drivers/types";
import { resolveMountMoveModalState } from "../mountMutationModalHelpers";
import type { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";

type BuildItemOverrides = Partial<Omit<MountExplorerItem, "mountMeta">> & {
  mountMeta?: Partial<MountExplorerItem["mountMeta"]>;
};

const buildItem = ({
  mountMeta,
  ...overrides
}: BuildItemOverrides = {}) =>
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
    abilities: {
      children_create: false,
      move: true,
      destroy: true,
    },
    mountMeta: {
      mountId: "mount-1",
      normalizedPath: "/docs/report.txt",
      entryType: "file",
      mountTitle: "Shared Docs",
      provider: "localfs",
      abilities: {
        children_list: false,
        create_folder: false,
        move: true,
        rename: true,
        destroy: true,
        upload: false,
        duplicate: false,
        download: true,
        preview: true,
        wopi: false,
        share_link_create: false,
      },
      ...mountMeta,
    },
    ...overrides,
  }) as MountExplorerItem;

describe("resolveMountMoveModalState", () => {
  it("filters destination folders and hides descendants of moved folders", () => {
    const folderItem = buildItem({
      id: "mount-entry:mount-1:/docs/folder",
      title: "folder",
      type: ItemType.FOLDER,
      mountMeta: {
        normalizedPath: "/docs/folder",
        entryType: "folder",
      },
    });

    const result = resolveMountMoveModalState({
      items: [folderItem],
      currentPath: "/docs",
      destinationEntries: [
        {
          name: "notes.txt",
          normalized_path: "/docs/notes.txt",
          entry_type: "file",
          abilities: {},
        } as never,
        {
          name: "folder",
          normalized_path: "/docs/folder",
          entry_type: "folder",
          abilities: {},
        } as never,
        {
          name: "child",
          normalized_path: "/docs/child",
          entry_type: "folder",
          abilities: {},
        } as never,
      ],
      isLoading: false,
      isError: false,
    });

    expect(result.childFolders.map((entry) => entry.normalized_path)).toEqual([
      "/docs/child",
    ]);
    expect(result.canSubmit).toBe(true);
    expect(result.movePreflightError).toBeNull();
  });

  it("keeps unsupported selection when browse data is unavailable", () => {
    const result = resolveMountMoveModalState({
      items: [buildItem()],
      currentPath: "/docs",
      destinationEntries: undefined,
      isLoading: false,
      isError: false,
    });

    expect(result.canSubmit).toBe(false);
    expect(result.movePreflightError).toEqual({
      ok: false,
      code: "unsupported_selection",
    });
  });

  it("surfaces target conflict and disables submit", () => {
    const result = resolveMountMoveModalState({
      items: [buildItem()],
      currentPath: "/archive",
      destinationEntries: [
        {
          name: "report.txt",
          normalized_path: "/archive/report.txt",
          entry_type: "file",
          abilities: {},
        } as never,
      ],
      isLoading: false,
      isError: false,
    });

    expect(result.canSubmit).toBe(false);
    expect(result.movePreflightError).toMatchObject({
      ok: false,
      code: "target_conflict",
      conflictingName: "report.txt",
    });
  });
});
