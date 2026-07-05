import { ItemType } from "@/features/drivers/types";
import {
  createFolderTargetEmbeddedExplorerProps,
  resolveCurrentFolderTarget,
} from "../folderTargetModalHelpers";

describe("folderTargetModalHelpers", () => {
  it("builds the shared embedded explorer preset for folder-target modals", () => {
    const breadcrumbsRight = jest.fn();
    const itemsFilter = jest.fn();
    const props = createFolderTargetEmbeddedExplorerProps({
      breadcrumbsRight,
      disableItemDragAndDrop: true,
      initialFolderId: "folder-1",
      itemsFilter,
    });

    expect(props).toMatchObject({
      breadcrumbsRight,
      initialFolderId: "folder-1",
      isCompact: true,
      itemsFilter,
      itemsFilters: {
        type: ItemType.FOLDER,
      },
      gridProps: {
        disableItemDragAndDrop: true,
        disableKeyboardNavigation: true,
        enableMetaKeySelection: false,
      },
    });
    expect(props.gridProps?.gridActionsCell?.({} as never)).toBeNull();
  });

  it("resolves the current folder target by preferring the selected folder over the current folder", () => {
    const selectedFolder = {
      id: "folder-selected",
      path: "root.folder-selected",
    };
    const currentFolder = {
      id: "folder-current",
      path: "root.folder-current",
    };

    expect(
      resolveCurrentFolderTarget({
        currentItem: currentFolder,
        currentItemId: currentFolder.id,
        selectedItems: [selectedFolder],
      }),
    ).toEqual({
      folderId: selectedFolder.id,
      folderItem: selectedFolder,
    });

    expect(
      resolveCurrentFolderTarget({
        currentItem: currentFolder,
        currentItemId: currentFolder.id,
        selectedItems: [],
      }),
    ).toEqual({
      folderId: currentFolder.id,
      folderItem: currentFolder,
    });
  });
});
