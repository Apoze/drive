import {
  buildArchiveViewerExtractPayload,
  getArchiveViewerDefaultDestinationFolderId,
} from "../archiveViewerExtractController";

describe("archiveViewerExtractController", () => {
  it("derives the default destination folder from the archive details path", () => {
    expect(
      getArchiveViewerDefaultDestinationFolderId(
        "drive.workspace.parent-folder.current-folder",
      ),
    ).toBe("parent-folder");
    expect(getArchiveViewerDefaultDestinationFolderId(undefined)).toBeUndefined();
  });

  it("builds an extract-all payload", () => {
    expect(
      buildArchiveViewerExtractPayload({
        archiveItemId: "archive-1",
        destinationFolderId: "folder-1",
        extractMode: "all",
      }),
    ).toEqual({
      destination_folder_id: "folder-1",
      item_id: "archive-1",
      mode: "all",
    });
  });

  it("builds a selection payload with the selected path", () => {
    expect(
      buildArchiveViewerExtractPayload({
        archiveItemId: "archive-1",
        destinationFolderId: "folder-1",
        extractMode: "selection",
        selectedPath: "docs/readme.txt",
      }),
    ).toEqual({
      destination_folder_id: "folder-1",
      item_id: "archive-1",
      mode: "selection",
      selection_paths: ["docs/readme.txt"],
    });
  });
});
