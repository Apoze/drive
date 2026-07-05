import {
  getArchiveEntryDisplayParts,
  getFilteredArchiveEntries,
  getNextArchiveSortState,
  getSortedArchiveEntries,
} from "../archiveViewerListController";

describe("archiveViewerListController", () => {
  it("computes display parts from nested paths", () => {
    expect(getArchiveEntryDisplayParts("docs/readme.txt")).toEqual({
      dir: "docs",
      name: "readme.txt",
    });
  });

  it("sorts archive entries by size then path", () => {
    expect(
      getSortedArchiveEntries({
        entries: [
          { isDirectory: false, path: "b/file.txt", uncompressedSize: 10 },
          { isDirectory: false, path: "a/file.txt", uncompressedSize: 10 },
          { isDirectory: false, path: "c/file.txt", uncompressedSize: 1 },
        ],
        sortDir: "asc",
        sortKey: "size",
      }).map((entry) => entry.path),
    ).toEqual(["c/file.txt", "a/file.txt", "b/file.txt"]);
  });

  it("filters archive entries by normalized query", () => {
    expect(
      getFilteredArchiveEntries({
        entries: [
          { isDirectory: false, path: "docs/readme.txt", uncompressedSize: 1 },
          { isDirectory: false, path: "images/photo.png", uncompressedSize: 1 },
        ],
        query: " READ ",
      }).map((entry) => entry.path),
    ).toEqual(["docs/readme.txt"]);
  });

  it("toggles sort direction and resets to asc on key change", () => {
    expect(
      getNextArchiveSortState({
        key: "name",
        sortDir: "asc",
        sortKey: "name",
      }),
    ).toEqual({
      sortDir: "desc",
      sortKey: "name",
    });

    expect(
      getNextArchiveSortState({
        key: "size",
        sortDir: "desc",
        sortKey: "name",
      }),
    ).toEqual({
      sortDir: "asc",
      sortKey: "size",
    });
  });
});
