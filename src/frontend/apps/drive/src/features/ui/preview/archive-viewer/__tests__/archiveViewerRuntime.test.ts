import { Archive } from "libarchive.js";
import { createArchiveZipWorker } from "../archiveZipWorkerFactory";
import { createArchiveViewerRuntime } from "../archiveViewerRuntime";

jest.mock("../archiveZipWorkerFactory", () => ({
  createArchiveZipWorker: jest.fn(),
}));

jest.mock("libarchive.js", () => ({
  Archive: {
    init: jest.fn(),
    open: jest.fn(),
  },
}));

const mockedCreateArchiveZipWorker = jest.mocked(createArchiveZipWorker);
const mockedArchive = jest.mocked(Archive);

describe("archiveViewerRuntime", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("routes zip list and reads through the worker session", async () => {
    const fakeWorker = {
      onmessage: null as ((event: MessageEvent) => void) | null,
      postMessage: jest.fn((payload: { requestId: number; type: string }) => {
        if (payload.type === "list") {
          fakeWorker.onmessage?.({
            data: {
              entries: [
                {
                  isDirectory: false,
                  path: "docs/readme.txt",
                  uncompressedSize: 12,
                },
                {
                  isDirectory: true,
                  path: "docs/",
                  uncompressedSize: 0,
                },
              ],
              requestId: payload.requestId,
              type: "list:ok",
            },
          } as MessageEvent);
          return;
        }
        if (payload.type === "readText") {
          fakeWorker.onmessage?.({
            data: {
              requestId: payload.requestId,
              text: "hello archive",
              type: "readText:ok",
            },
          } as MessageEvent);
          return;
        }
        fakeWorker.onmessage?.({
          data: {
            buffer: new ArrayBuffer(4),
            requestId: payload.requestId,
            type: "readBinary:ok",
          },
        } as MessageEvent);
      }),
      terminate: jest.fn(),
    };
    mockedCreateArchiveZipWorker.mockReturnValue(fakeWorker as never);

    const runtime = createArchiveViewerRuntime();
    const loaded = await runtime.loadEntries({
      archiveAccessMode: "auto",
      archiveItem: {
        id: "archive-1",
        mimetype: "application/zip",
        size: 10,
        title: "demo.zip",
        url: "https://example.test/archive.zip",
      },
      encryptedArchiveMessage: "encrypted",
      maxBlobBytes: 100,
      previewTooLargeMessage: "too-large",
    });

    const text = await runtime.readTextEntry({
      backend: loaded.backend,
      path: "docs/readme.txt",
      unsupportedPreviewMessage: "unsupported",
      url: "https://example.test/archive.zip",
    });

    expect(loaded).toEqual({
      backend: "zip",
      entries: [
        {
          isDirectory: false,
          path: "docs/readme.txt",
          uncompressedSize: 12,
        },
      ],
    });
    expect(text).toBe("hello archive");
    expect(fakeWorker.postMessage).toHaveBeenCalledTimes(2);
    expect(fakeWorker.terminate).not.toHaveBeenCalled();
    runtime.dispose();
    expect(fakeWorker.terminate).toHaveBeenCalledTimes(1);
  });

  it("opens libarchive archives and reads binary entries without the worker", async () => {
    const extract = jest.fn().mockResolvedValue(new Blob(["img"]));
    mockedArchive.open.mockResolvedValue({
      getFilesArray: jest.fn().mockResolvedValue([
        {
          file: {
            extract,
            name: "photo.png",
            size: 3,
          },
          path: "images/",
        },
      ]),
      hasEncryptedData: jest.fn().mockResolvedValue(false),
    } as never);

    const originalFetch = global.fetch;
    global.fetch = jest.fn().mockResolvedValue({
      blob: jest.fn().mockResolvedValue(new Blob(["archive"])),
      ok: true,
    }) as never;

    const runtime = createArchiveViewerRuntime();
    const loaded = await runtime.loadEntries({
      archiveAccessMode: "download",
      archiveItem: {
        id: "archive-2",
        mimetype: "application/x-tar",
        size: 10,
        title: "demo.tar",
        url: "https://example.test/archive.tar",
      },
      encryptedArchiveMessage: "encrypted",
      maxBlobBytes: 100,
      previewTooLargeMessage: "too-large",
    });

    const blob = await runtime.readBinaryEntry({
      backend: loaded.backend,
      path: "images/photo.png",
      unsupportedPreviewMessage: "unsupported",
      url: "https://example.test/archive.tar",
    });

    expect(loaded).toEqual({
      backend: "libarchive",
      entries: [
        {
          isDirectory: false,
          lastModified: null,
          path: "images/photo.png",
          uncompressedSize: 3,
        },
      ],
    });
    expect(mockedArchive.init).toHaveBeenCalledWith({
      workerUrl: "/vendor/libarchive/worker-bundle.js",
    });
    expect(mockedArchive.open).toHaveBeenCalled();
    expect(extract).toHaveBeenCalledTimes(1);
    expect(blob).toBeInstanceOf(Blob);

    global.fetch = originalFetch;
  });
});
