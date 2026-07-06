import { FileWithPath, fromEvent } from "file-selector";

export const EMPTY_FOLDER_MARKER_NAME = ".empty-folder";

const EMPTY_FOLDER_MARKER_TYPE = "application/x-empty-folder-marker";

export type EmptyFolderMarker = FileWithPath & { isEmptyFolder: true };

export const createEmptyFolderMarker = (
  dirPath: string,
): EmptyFolderMarker => {
  const marker = new File([], EMPTY_FOLDER_MARKER_NAME, {
    type: EMPTY_FOLDER_MARKER_TYPE,
  }) as EmptyFolderMarker;
  Object.defineProperty(marker, "path", {
    value: `${dirPath}/${EMPTY_FOLDER_MARKER_NAME}`,
    writable: false,
    enumerable: true,
    configurable: true,
  });
  Object.defineProperty(marker, "isEmptyFolder", {
    value: true,
    writable: false,
    enumerable: true,
    configurable: true,
  });
  return marker;
};

export const isEmptyFolderMarker = (file: File): boolean => {
  return (file as EmptyFolderMarker).isEmptyFolder === true;
};

export const readAllEntries = (
  reader: FileSystemDirectoryReader,
): Promise<FileSystemEntry[]> => {
  return new Promise((resolve, reject) => {
    const allEntries: FileSystemEntry[] = [];
    const readBatch = () => {
      reader.readEntries(
        (batch) => {
          if (batch.length === 0) {
            resolve(allEntries);
            return;
          }
          allEntries.push(...batch);
          readBatch();
        },
        (error) => reject(error),
      );
    };
    readBatch();
  });
};

export const getFileFromEntry = (
  entry: FileSystemFileEntry,
): Promise<FileWithPath> => {
  return new Promise((resolve, reject) => {
    entry.file(
      (file) => {
        const fileWithPath = file as FileWithPath;
        Object.defineProperty(fileWithPath, "path", {
          value: entry.fullPath,
          writable: false,
          enumerable: true,
          configurable: true,
        });
        resolve(fileWithPath);
      },
      (error) => reject(error),
    );
  });
};

export const traverseEntry = async (
  entry: FileSystemEntry,
): Promise<(FileWithPath | EmptyFolderMarker)[]> => {
  if (entry.isFile) {
    return [await getFileFromEntry(entry as FileSystemFileEntry)];
  }

  if (entry.isDirectory) {
    const directory = entry as FileSystemDirectoryEntry;
    const children = await readAllEntries(directory.createReader());
    if (children.length === 0) {
      return [createEmptyFolderMarker(directory.fullPath)];
    }
    const nestedEntries = await Promise.all(children.map(traverseEntry));
    return nestedEntries.flat();
  }

  return [];
};

const isDragEventWithItems = (
  event: unknown,
): event is { dataTransfer: DataTransfer; type?: string } => {
  if (typeof event !== "object" || event === null) {
    return false;
  }
  const dataTransfer = (event as { dataTransfer?: DataTransfer }).dataTransfer;
  return !!dataTransfer?.items;
};

export const customGetFilesFromEvent = async (
  event: unknown,
): Promise<(FileWithPath | EmptyFolderMarker | DataTransferItem)[]> => {
  if (!isDragEventWithItems(event)) {
    return fromEvent(event as Event);
  }

  const items = Array.from(event.dataTransfer.items).filter(
    (item) => item.kind === "file",
  );
  if (event.type !== "drop") {
    return items;
  }

  const supportsEntries = items.every(
    (item) => typeof item.webkitGetAsEntry === "function",
  );
  if (!supportsEntries) {
    return fromEvent(event as unknown as Event);
  }

  const entries: FileSystemEntry[] = [];
  for (const item of items) {
    const entry = item.webkitGetAsEntry();
    if (entry) {
      entries.push(entry);
    }
  }

  const walkedEntries = await Promise.all(entries.map(traverseEntry));
  return walkedEntries.flat();
};
