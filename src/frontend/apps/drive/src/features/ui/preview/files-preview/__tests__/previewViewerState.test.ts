import { MimeCategory } from "@/features/explorer/utils/mimeTypes";
import type { FilePreviewType } from "../previewSource";
import { resolvePreviewViewerKind } from "../previewViewerState";

const buildFile = (
  overrides: Partial<FilePreviewType> & { category?: MimeCategory } = {},
) =>
  ({
    id: "file-1",
    size: 128,
    title: "demo",
    filename: "demo.txt",
    mimetype: "text/plain",
    url_preview: "https://example.test/preview",
    category: MimeCategory.OTHER,
    ...overrides,
  }) as FilePreviewType & { category: MimeCategory };

describe("resolvePreviewViewerKind", () => {
  it("covers the main viewer routing decisions for the generic preview host", () => {
    expect(
      resolvePreviewViewerKind({
        currentFile: undefined,
        effectiveCurrentFile: undefined,
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("empty");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: true },
        effectiveCurrentFile: buildFile(),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("suspicious");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile(),
        isResolvingCurrentFile: true,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("resolving");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile(),
        isResolvingCurrentFile: false,
        hasResolveError: true,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("resolve_error");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile({ preview_kind: "unsupported" }),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("unsupported_kind");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile(),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: true,
        shouldRenderWopi: false,
      }),
    ).toBe("text");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile(),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: true,
      }),
    ).toBe("wopi");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile({
          category: MimeCategory.IMAGE,
          url_preview: undefined,
        }),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("missing_url");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile({
          category: MimeCategory.IMAGE,
          mimetype: "image/heic",
        }),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("unsupported_heic");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile({ category: MimeCategory.IMAGE }),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("image");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile({
          category: MimeCategory.VIDEO,
          mimetype: "video/mp4",
        }),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("video");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile({
          category: MimeCategory.AUDIO,
          mimetype: "audio/mpeg",
        }),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("audio");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile({
          category: MimeCategory.PDF,
          mimetype: "application/pdf",
          url_preview: undefined,
          url: "https://example.test/original.pdf",
        }),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("pdf");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile({
          category: MimeCategory.PDF,
          mimetype: "application/pdf",
          url_preview: undefined,
          url: undefined,
          stream_url: undefined,
        }),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("missing_url");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile({
          category: MimeCategory.ARCHIVE,
          mimetype: "application/zip",
          url_preview: undefined,
        }),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("archive");

    expect(
      resolvePreviewViewerKind({
        currentFile: { isSuspicious: false },
        effectiveCurrentFile: buildFile({
          category: MimeCategory.OTHER,
          mimetype: "application/octet-stream",
        }),
        isResolvingCurrentFile: false,
        hasResolveError: false,
        useTextViewer: false,
        shouldRenderWopi: false,
      }),
    ).toBe("unsupported");
  });
});
