import {
  getArchiveEntryDownload,
  loadArchiveEntryPreview,
} from "../archiveViewerPreviewController";

describe("archiveViewerPreviewController", () => {
  it("loads text previews through the runtime", async () => {
    const runtime = {
      readTextEntry: jest.fn().mockResolvedValue("hello archive"),
    };

    await expect(
      loadArchiveEntryPreview({
        backend: "zip",
        entry: {
          isDirectory: false,
          path: "docs/readme.txt",
          uncompressedSize: 10,
        },
        runtime: runtime as never,
        tooLargeToPreviewImageMessage: "image-too-large",
        tooLargeToPreviewTextMessage: "text-too-large",
        unsupportedPreviewMessage: "unsupported",
        url: "https://example.test/archive.zip",
      }),
    ).resolves.toEqual({
      kind: "text",
      text: "hello archive",
    });
    expect(runtime.readTextEntry).toHaveBeenCalledWith({
      backend: "zip",
      path: "docs/readme.txt",
      unsupportedPreviewMessage: "unsupported",
      url: "https://example.test/archive.zip",
    });
  });

  it("rejects oversized text previews before runtime access", async () => {
    const runtime = {
      readTextEntry: jest.fn(),
    };

    await expect(
      loadArchiveEntryPreview({
        backend: "zip",
        entry: {
          isDirectory: false,
          path: "docs/readme.txt",
          uncompressedSize: 300 * 1024,
        },
        runtime: runtime as never,
        tooLargeToPreviewImageMessage: "image-too-large",
        tooLargeToPreviewTextMessage: "text-too-large",
        unsupportedPreviewMessage: "unsupported",
        url: "https://example.test/archive.zip",
      }),
    ).resolves.toEqual({
      error: "text-too-large",
      kind: "empty",
    });
    expect(runtime.readTextEntry).not.toHaveBeenCalled();
  });

  it("loads image previews through the runtime", async () => {
    const blob = new Blob(["img"]);
    const runtime = {
      readBinaryEntry: jest.fn().mockResolvedValue(blob),
    };

    await expect(
      loadArchiveEntryPreview({
        backend: "libarchive",
        entry: {
          isDirectory: false,
          path: "images/photo.png",
          uncompressedSize: 10,
        },
        runtime: runtime as never,
        tooLargeToPreviewImageMessage: "image-too-large",
        tooLargeToPreviewTextMessage: "text-too-large",
        unsupportedPreviewMessage: "unsupported",
        url: "https://example.test/archive.tar",
      }),
    ).resolves.toEqual({
      blob,
      kind: "image",
    });
  });

  it("computes selected-entry downloads through the runtime", async () => {
    const blob = new Blob(["file"]);
    const runtime = {
      readBinaryEntry: jest.fn().mockResolvedValue(blob),
    };

    await expect(
      getArchiveEntryDownload({
        backend: "zip",
        entry: {
          isDirectory: false,
          path: "docs/readme.txt",
          uncompressedSize: 10,
        },
        runtime: runtime as never,
        unsupportedPreviewMessage: "unsupported",
        url: "https://example.test/archive.zip",
      }),
    ).resolves.toEqual({
      blob,
      filename: "readme.txt",
    });
  });
});
