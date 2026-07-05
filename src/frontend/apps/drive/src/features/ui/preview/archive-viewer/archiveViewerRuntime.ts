import { createArchiveZipWorker } from "./archiveZipWorkerFactory";

export type ArchiveItem = {
  id: string;
  title: string;
  size: number;
  mimetype: string;
  url?: string;
};

export type ArchiveEntry = {
  path: string;
  isDirectory: boolean;
  uncompressedSize: number;
  compressedSize?: number;
  lastModified?: number | null;
};

export type ArchiveBackend = "zip" | "libarchive" | "none";

type ZipWorkerRequest =
  | { requestId: number; type: "list"; url: string }
  | { requestId: number; type: "readText"; url: string; path: string }
  | { requestId: number; type: "readBinary"; url: string; path: string };

type ZipWorkerRequestWithoutId =
  | { type: "list"; url: string }
  | { type: "readText"; url: string; path: string }
  | { type: "readBinary"; url: string; path: string };

type ZipWorkerResponse =
  | { requestId: number; type: "list:ok"; entries: ArchiveEntry[] }
  | { requestId: number; type: "readText:ok"; text: string }
  | { requestId: number; type: "readBinary:ok"; buffer: ArrayBuffer }
  | { requestId: number; type: "error"; message: string; code?: string };

type LibarchiveFile = {
  name?: string;
  size?: number;
  lastModified?: number;
  extract?: () => Promise<Blob>;
};

type LibarchiveArchive = {
  hasEncryptedData: () => Promise<boolean>;
  getFilesArray: () => Promise<Array<{ file: LibarchiveFile; path: string }>>;
};

type PendingWorkerRequest = {
  resolve: (value: ZipWorkerResponse) => void;
  reject: (error: Error) => void;
};

const isZipLike = (item: ArchiveItem) => {
  const name = item.title.toLowerCase();
  if (name.endsWith(".zip")) return true;
  if (item.mimetype === "application/zip") return true;
  return false;
};

export const createArchiveViewerRuntime = () => {
  let worker: Worker | null = null;
  let nextRequestId = 1;
  const pending = new Map<number, PendingWorkerRequest>();
  let libarchive: {
    archive: LibarchiveArchive;
    fileByPath: Map<string, LibarchiveFile>;
  } | null = null;
  let libarchiveInit = false;

  const reset = (message: string) => {
    if (worker) {
      worker.terminate();
      worker = null;
    }
    for (const request of pending.values()) {
      request.reject(new Error(message));
    }
    pending.clear();
    nextRequestId = 1;
    libarchive = null;
  };

  const ensureWorker = () => {
    if (worker) return worker;
    const nextWorker = createArchiveZipWorker();
    nextWorker.onmessage = (event: MessageEvent<ZipWorkerResponse>) => {
      const request = pending.get(event.data.requestId);
      if (!request) return;
      pending.delete(event.data.requestId);
      request.resolve(event.data);
    };
    worker = nextWorker;
    return nextWorker;
  };

  const callWorker = async (payload: ZipWorkerRequestWithoutId) => {
    const currentWorker = ensureWorker();
    const requestId = nextRequestId++;
    const response = await new Promise<ZipWorkerResponse>((resolve, reject) => {
      pending.set(requestId, { resolve, reject });
      currentWorker.postMessage({ ...payload, requestId } as ZipWorkerRequest);
    });
    if (response.type === "error") {
      throw new Error(response.message);
    }
    return response;
  };

  const ensureLibarchiveInit = async () => {
    if (libarchiveInit) return;
    const { Archive } = await import("libarchive.js");
    Archive.init({
      workerUrl: "/vendor/libarchive/worker-bundle.js",
    });
    libarchiveInit = true;
  };

  const loadEntries = async ({
    archiveAccessMode,
    archiveItem,
    encryptedArchiveMessage,
    maxBlobBytes,
    previewTooLargeMessage,
  }: {
    archiveAccessMode: "auto" | "download";
    archiveItem: ArchiveItem;
    encryptedArchiveMessage: string;
    maxBlobBytes: number;
    previewTooLargeMessage: string;
  }): Promise<{ backend: Exclude<ArchiveBackend, "none">; entries: ArchiveEntry[] }> => {
    const url = archiveItem.url;
    if (!url) {
      throw new Error("Archive URL is missing.");
    }

    reset("Archive source changed.");

    const shouldUseZipRangeBackend =
      isZipLike(archiveItem) && archiveAccessMode !== "download";
    if (shouldUseZipRangeBackend) {
      const response = await callWorker({ type: "list", url });
      if (response.type !== "list:ok") {
        throw new Error("Unsupported archive worker response.");
      }
      return {
        backend: "zip",
        entries: response.entries.filter((entry) => !entry.isDirectory),
      };
    }

    if (Number(archiveItem.size ?? 0) > maxBlobBytes) {
      throw new Error(previewTooLargeMessage);
    }

    await ensureLibarchiveInit();
    const response = await fetch(url, { credentials: "include" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const { Archive } = await import("libarchive.js");
    const file = new File([blob], archiveItem.title || "archive", {
      type: archiveItem.mimetype || "application/octet-stream",
    });
    const archive = (await Archive.open(file)) as unknown as LibarchiveArchive;
    const encrypted = await archive.hasEncryptedData();
    if (encrypted) {
      throw new Error(encryptedArchiveMessage);
    }
    const filesArray = await archive.getFilesArray();
    const fileByPath = new Map<string, LibarchiveFile>();
    const entries = filesArray
      .map(({ file, path }) => {
        const dir = path ?? "";
        const name = file?.name ?? "";
        const full = `${dir}${name}`;
        fileByPath.set(full, file);
        return {
          path: full,
          isDirectory: Boolean(full.endsWith("/")),
          uncompressedSize: Number(file?.size ?? 0),
          lastModified: file?.lastModified
            ? new Date(file.lastModified).getTime()
            : null,
        };
      })
      .filter((entry) => entry.path && !entry.isDirectory);
    libarchive = { archive, fileByPath };
    return {
      backend: "libarchive",
      entries,
    };
  };

  const readTextEntry = async ({
    backend,
    path,
    unsupportedPreviewMessage,
    url,
  }: {
    backend: Exclude<ArchiveBackend, "none">;
    path: string;
    unsupportedPreviewMessage: string;
    url: string;
  }) => {
    if (backend === "zip") {
      const response = await callWorker({ type: "readText", url, path });
      if (response.type !== "readText:ok") {
        throw new Error("Unsupported archive worker response.");
      }
      return response.text;
    }

    const file = libarchive?.fileByPath.get(path);
    if (!file?.extract) {
      throw new Error(unsupportedPreviewMessage);
    }
    const extracted = await file.extract();
    return extracted.text();
  };

  const readBinaryEntry = async ({
    backend,
    path,
    unsupportedPreviewMessage,
    url,
  }: {
    backend: Exclude<ArchiveBackend, "none">;
    path: string;
    unsupportedPreviewMessage: string;
    url: string;
  }) => {
    if (backend === "zip") {
      const response = await callWorker({ type: "readBinary", url, path });
      if (response.type !== "readBinary:ok") {
        throw new Error("Unsupported archive worker response.");
      }
      return new Blob([response.buffer]);
    }

    const file = libarchive?.fileByPath.get(path);
    if (!file?.extract) {
      throw new Error(unsupportedPreviewMessage);
    }
    return file.extract();
  };

  return {
    dispose: () => {
      reset("Archive viewer unmounted.");
    },
    loadEntries,
    readBinaryEntry,
    readTextEntry,
    reset,
  };
};
