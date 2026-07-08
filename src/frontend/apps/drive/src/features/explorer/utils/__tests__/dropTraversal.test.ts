import {
  createEmptyFolderMarker,
  EMPTY_FOLDER_MARKER_NAME,
  getFileFromEntry,
  isEmptyFolderMarker,
  readAllEntries,
  traverseEntry,
} from "../dropTraversal";

const makeFileEntry = (
  fullPath: string,
  content = "",
): FileSystemFileEntry => {
  const name = fullPath.split("/").pop() ?? "";
  const file = new File([content], name, { type: "text/plain" });
  return {
    isFile: true,
    isDirectory: false,
    name,
    fullPath,
    file: (success: FileCallback) => success(file),
  } as unknown as FileSystemFileEntry;
};

const makeFailingFileEntry = (
  fullPath: string,
  error: unknown,
): FileSystemFileEntry => {
  const name = fullPath.split("/").pop() ?? "";
  return {
    isFile: true,
    isDirectory: false,
    name,
    fullPath,
    file: (_success: FileCallback, errorCallback?: ErrorCallback) => {
      errorCallback?.(error as DOMException);
    },
  } as unknown as FileSystemFileEntry;
};

const makeReader = (
  batches: FileSystemEntry[][],
): FileSystemDirectoryReader => {
  const queue = [...batches];
  return {
    readEntries: (success: FileSystemEntriesCallback) => {
      success(queue.shift() ?? []);
    },
  } as FileSystemDirectoryReader;
};

const makeFailingReader = (error: unknown): FileSystemDirectoryReader => {
  return {
    readEntries: (
      _success: FileSystemEntriesCallback,
      errorCallback?: ErrorCallback,
    ) => {
      errorCallback?.(error as DOMException);
    },
  } as FileSystemDirectoryReader;
};

const makeDirEntry = (
  fullPath: string,
  children: FileSystemEntry[],
): FileSystemDirectoryEntry => {
  const name = fullPath.split("/").pop() ?? "";
  return {
    isFile: false,
    isDirectory: true,
    name,
    fullPath,
    createReader: () => makeReader([children, []]),
  } as unknown as FileSystemDirectoryEntry;
};

describe("dropTraversal", () => {
  it("creates flagged zero-byte empty-folder markers", () => {
    const marker = createEmptyFolderMarker("/folder/empty");

    expect(marker).toBeInstanceOf(File);
    expect(marker.size).toBe(0);
    expect(marker.name).toBe(EMPTY_FOLDER_MARKER_NAME);
    expect(marker.path).toBe(`/folder/empty/${EMPTY_FOLDER_MARKER_NAME}`);
    expect(isEmptyFolderMarker(marker)).toBe(true);
    expect(isEmptyFolderMarker(new File([], EMPTY_FOLDER_MARKER_NAME))).toBe(
      false,
    );
  });

  it("resolves files from entries and preserves fullPath", async () => {
    const file = await getFileFromEntry(makeFileEntry("/dir/file.txt", "hello"));

    expect(file.name).toBe("file.txt");
    expect(file.size).toBe(5);
    expect(file.path).toBe("/dir/file.txt");
  });

  it("rejects when file entry resolution fails", async () => {
    const error = new DOMException("nope", "NotReadableError");
    await expect(
      getFileFromEntry(makeFailingFileEntry("/bad.txt", error)),
    ).rejects.toBe(error);
  });

  it("reads all directory entry batches", async () => {
    const one = makeFileEntry("/one.txt");
    const two = makeFileEntry("/two.txt");
    const three = makeFileEntry("/three.txt");

    await expect(readAllEntries(makeReader([[one], [two, three], []]))).resolves
      .toEqual([one, two, three]);
  });

  it("rejects when directory reading fails", async () => {
    const error = new DOMException("boom", "NotReadableError");

    await expect(readAllEntries(makeFailingReader(error))).rejects.toBe(error);
  });

  it("traverses files, non-empty directories, and empty leaf folders", async () => {
    const root = makeDirEntry("/root", [
      makeDirEntry("/root/empty", []),
      makeDirEntry("/root/nested", [
        makeDirEntry("/root/nested/empty-leaf", []),
        makeFileEntry("/root/nested/file.txt", "x"),
      ]),
    ]);

    const result = await traverseEntry(root);
    const realPaths = (result as Array<File & { path: string }>)
      .filter((file) => !isEmptyFolderMarker(file))
      .map((file) => file.path)
      .sort((a, b) => a.localeCompare(b));
    const markerPaths = (result as Array<File & { path: string }>)
      .filter((file) => isEmptyFolderMarker(file))
      .map((file) => file.path)
      .sort((a, b) => a.localeCompare(b));

    expect(realPaths).toEqual(["/root/nested/file.txt"]);
    expect(markerPaths).toEqual([
      `/root/empty/${EMPTY_FOLDER_MARKER_NAME}`,
      `/root/nested/empty-leaf/${EMPTY_FOLDER_MARKER_NAME}`,
    ]);
  });

  it("returns an empty list for entries that are neither files nor directories", async () => {
    await expect(
      traverseEntry({
        isFile: false,
        isDirectory: false,
        name: "unknown",
        fullPath: "/unknown",
      } as unknown as FileSystemEntry),
    ).resolves.toEqual([]);
  });
});
