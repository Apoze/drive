const zipReaderInstances: Array<{
  source: unknown;
  close: jest.Mock<Promise<void>, []>;
  getEntries: jest.Mock<Promise<unknown[]>, []>;
}> = [];

let rangeEntries: unknown[] = [];
let blobEntries: unknown[] = [];
let rangeOpenError: Error | null = null;
let blobOpenError: Error | null = null;

class MockHttpRangeReader {
  constructor(
    public readonly url: string,
    public readonly options: unknown,
  ) {}
}

class MockBlobReader {
  constructor(public readonly blob: Blob) {}
}

class MockTextWriter {}
class MockUint8ArrayWriter {}

jest.mock("@zip.js/zip.js", () => ({
  BlobReader: MockBlobReader,
  HttpRangeReader: MockHttpRangeReader,
  TextWriter: MockTextWriter,
  Uint8ArrayWriter: MockUint8ArrayWriter,
  ZipReader: jest.fn().mockImplementation((source: unknown) => {
    if (source instanceof MockHttpRangeReader) {
      if (rangeOpenError) {
        throw rangeOpenError;
      }
      const instance = {
        source,
        close: jest.fn().mockResolvedValue(undefined),
        getEntries: jest.fn().mockResolvedValue(rangeEntries),
      };
      zipReaderInstances.push(instance);
      return instance;
    }

    if (source instanceof MockBlobReader) {
      if (blobOpenError) {
        throw blobOpenError;
      }
      const instance = {
        source,
        close: jest.fn().mockResolvedValue(undefined),
        getEntries: jest.fn().mockResolvedValue(blobEntries),
      };
      zipReaderInstances.push(instance);
      return instance;
    }

    throw new Error("Unsupported reader source.");
  }),
}));

type FakeWorkerSelf = {
  onmessage: ((event: { data: unknown }) => Promise<void> | void) | null;
  postMessage: jest.Mock<void, [unknown, ArrayBuffer[]?]>;
};

const createZipEntry = ({
  filename,
  directory = false,
  text = "archive text",
  binary = new Uint8Array([1, 2, 3]),
  uncompressedSize = 12,
  compressedSize = 7,
  lastModDate = new Date("2026-03-31T00:00:00Z"),
}: {
  filename: string;
  directory?: boolean;
  text?: string;
  binary?: Uint8Array;
  uncompressedSize?: number;
  compressedSize?: number;
  lastModDate?: Date | null;
}) => ({
  filename,
  directory,
  uncompressedSize,
  compressedSize,
  lastModDate,
  getData: jest.fn(async (writer: unknown) => {
    if (writer instanceof MockTextWriter) {
      return text;
    }
    if (writer instanceof MockUint8ArrayWriter) {
      return binary;
    }
    throw new Error("Unsupported writer.");
  }),
});

const importWorker = async () => {
  jest.resetModules();
  zipReaderInstances.length = 0;
  const workerSelf: FakeWorkerSelf = {
    onmessage: null,
    postMessage: jest.fn(),
  };
  ((globalThis as unknown) as { self?: FakeWorkerSelf }).self = workerSelf;
  await import("../workers/zip.worker");
  return workerSelf;
};

describe("zip.worker", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    rangeEntries = [];
    blobEntries = [];
    rangeOpenError = null;
    blobOpenError = null;
    global.fetch = jest.fn() as never;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("lists archive entries and reuses the opened range reader for subsequent text reads", async () => {
    rangeEntries = [
      createZipEntry({
        filename: "docs/readme.txt",
        text: "hello archive",
        uncompressedSize: 12,
        compressedSize: 5,
      }),
      createZipEntry({
        filename: "docs/",
        directory: true,
        uncompressedSize: 0,
        compressedSize: 0,
      }),
    ];

    const workerSelf = await importWorker();

    await workerSelf.onmessage?.({
      data: { requestId: 1, type: "list", url: "https://example.test/archive.zip" },
    });
    await workerSelf.onmessage?.({
      data: {
        requestId: 2,
        type: "readText",
        url: "https://example.test/archive.zip",
        path: "docs/readme.txt",
      },
    });

    expect(zipReaderInstances).toHaveLength(1);
    expect(workerSelf.postMessage).toHaveBeenNthCalledWith(1, {
      requestId: 1,
      type: "list:ok",
      entries: [
        {
          path: "docs/readme.txt",
          isDirectory: false,
          uncompressedSize: 12,
          compressedSize: 5,
          lastModified: new Date("2026-03-31T00:00:00Z").getTime(),
        },
        {
          path: "docs/",
          isDirectory: true,
          uncompressedSize: 0,
          compressedSize: 0,
          lastModified: new Date("2026-03-31T00:00:00Z").getTime(),
        },
      ],
    });
    expect(workerSelf.postMessage).toHaveBeenNthCalledWith(2, {
      requestId: 2,
      type: "readText:ok",
      text: "hello archive",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("transfers binary reads through the worker response contract", async () => {
    const binary = new Uint8Array([9, 8, 7, 6]);
    rangeEntries = [
      createZipEntry({
        filename: "images/photo.png",
        binary,
      }),
    ];
    const workerSelf = await importWorker();

    await workerSelf.onmessage?.({
      data: {
        requestId: 3,
        type: "readBinary",
        url: "https://example.test/archive.zip",
        path: "images/photo.png",
      },
    });

    const [message, transfer] = workerSelf.postMessage.mock.calls[0];
    expect(message).toMatchObject({
      requestId: 3,
      type: "readBinary:ok",
      buffer: expect.any(ArrayBuffer),
    });
    expect(new Uint8Array((message as { buffer: ArrayBuffer }).buffer)).toEqual(binary);
    expect(transfer).toHaveLength(1);
    expect(transfer?.[0]).toBe((message as { buffer: ArrayBuffer }).buffer);
  });

  it("keeps file-not-found errors stable for missing or directory archive entries", async () => {
    rangeEntries = [
      createZipEntry({
        filename: "docs/",
        directory: true,
      }),
    ];
    const workerSelf = await importWorker();

    await workerSelf.onmessage?.({
      data: {
        requestId: 4,
        type: "readText",
        url: "https://example.test/archive.zip",
        path: "docs/",
      },
    });
    await workerSelf.onmessage?.({
      data: {
        requestId: 5,
        type: "readBinary",
        url: "https://example.test/archive.zip",
        path: "missing.bin",
      },
    });

    expect(workerSelf.postMessage).toHaveBeenNthCalledWith(1, {
      requestId: 4,
      type: "error",
      message: "File not found in archive.",
    });
    expect(workerSelf.postMessage).toHaveBeenNthCalledWith(2, {
      requestId: 5,
      type: "error",
      message: "File not found in archive.",
    });
  });

  it("falls back to a bounded full download when range reads fail for a small archive", async () => {
    rangeOpenError = new Error("range unavailable");
    blobEntries = [
      createZipEntry({
        filename: "fallback/readme.txt",
        text: "small fallback",
      }),
    ];
    const workerSelf = await importWorker();
    const blob = new Blob(["archive"]);
    const fetchMock = jest.mocked(global.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        headers: {
          get: (name: string) => (name === "Content-Length" ? "1024" : null),
        },
      } as never)
      .mockResolvedValueOnce({
        ok: true,
        blob: jest.fn().mockResolvedValue(blob),
      } as never);

    await workerSelf.onmessage?.({
      data: { requestId: 6, type: "list", url: "https://example.test/archive.zip" },
    });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "https://example.test/archive.zip", {
      method: "HEAD",
      credentials: "include",
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "https://example.test/archive.zip", {
      credentials: "include",
    });
    expect(zipReaderInstances).toHaveLength(1);
    expect(zipReaderInstances[0]?.source).toBeInstanceOf(MockBlobReader);
    expect(workerSelf.postMessage).toHaveBeenCalledWith({
      requestId: 6,
      type: "list:ok",
      entries: [
        {
          path: "fallback/readme.txt",
          isDirectory: false,
          uncompressedSize: 12,
          compressedSize: 7,
          lastModified: new Date("2026-03-31T00:00:00Z").getTime(),
        },
      ],
    });
  });

  it.each([
    {
      name: "archive size is unknown",
      headResponse: {
        ok: true,
        headers: {
          get: () => null,
        },
      },
    },
    {
      name: "archive size exceeds the bounded fallback threshold",
      headResponse: {
        ok: true,
        headers: {
          get: (header: string) =>
            header === "Content-Length" ? String(51 * 1024 * 1024) : null,
        },
      },
    },
  ])("refuses the full-download fallback when $name", async ({ headResponse }) => {
    rangeOpenError = new Error("range unavailable");
    const workerSelf = await importWorker();
    const fetchMock = jest.mocked(global.fetch);
    fetchMock.mockResolvedValueOnce(headResponse as never);

    await workerSelf.onmessage?.({
      data: { requestId: 7, type: "list", url: "https://example.test/archive.zip" },
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(workerSelf.postMessage).toHaveBeenCalledWith({
      requestId: 7,
      type: "error",
      message: "Preview unavailable (Range required).",
    });
  });

  it("returns a stable unsupported-message error for unknown worker requests", async () => {
    const workerSelf = await importWorker();

    await workerSelf.onmessage?.({
      data: { requestId: 8, type: "unsupported" },
    });

    expect(workerSelf.postMessage).toHaveBeenCalledWith({
      requestId: 8,
      type: "error",
      message: "Unsupported worker message.",
    });
  });
});
