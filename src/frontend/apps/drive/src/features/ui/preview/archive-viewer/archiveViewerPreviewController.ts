import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ArchiveBackend,
  ArchiveEntry,
  createArchiveViewerRuntime,
} from "./archiveViewerRuntime";

const MAX_TEXT_PREVIEW_BYTES = 200 * 1024;
const MAX_IMAGE_PREVIEW_BYTES = 10 * 1024 * 1024;

export type ArchiveViewerPreviewKind = "empty" | "text" | "image";

const isImagePath = (path: string) => {
  const lower = path.toLowerCase();
  return (
    lower.endsWith(".png") ||
    lower.endsWith(".jpg") ||
    lower.endsWith(".jpeg") ||
    lower.endsWith(".gif") ||
    lower.endsWith(".webp") ||
    lower.endsWith(".bmp") ||
    lower.endsWith(".svg")
  );
};

const isTextPath = (path: string) => {
  const lower = path.toLowerCase();
  return (
    lower.endsWith(".txt") ||
    lower.endsWith(".md") ||
    lower.endsWith(".csv") ||
    lower.endsWith(".log") ||
    lower.endsWith(".json") ||
    lower.endsWith(".xml") ||
    lower.endsWith(".yaml") ||
    lower.endsWith(".yml") ||
    lower.endsWith(".js") ||
    lower.endsWith(".ts") ||
    lower.endsWith(".css") ||
    lower.endsWith(".scss") ||
    lower.endsWith(".py") ||
    lower.endsWith(".java") ||
    lower.endsWith(".go") ||
    lower.endsWith(".rs")
  );
};

type ArchiveViewerRuntime = ReturnType<typeof createArchiveViewerRuntime>;

export const loadArchiveEntryPreview = async ({
  backend,
  entry,
  runtime,
  tooLargeToPreviewImageMessage,
  tooLargeToPreviewTextMessage,
  unsupportedPreviewMessage,
  url,
}: {
  backend: Exclude<ArchiveBackend, "none">;
  entry: ArchiveEntry;
  runtime: ArchiveViewerRuntime;
  tooLargeToPreviewImageMessage: string;
  tooLargeToPreviewTextMessage: string;
  unsupportedPreviewMessage: string;
  url: string;
}) => {
  const path = entry.path;

  if (isTextPath(path)) {
    if (entry.uncompressedSize > MAX_TEXT_PREVIEW_BYTES) {
      return {
        error: tooLargeToPreviewTextMessage,
        kind: "empty" as const,
      };
    }

    const text = await runtime.readTextEntry({
      backend,
      path,
      unsupportedPreviewMessage,
      url,
    });
    return {
      kind: "text" as const,
      text,
    };
  }

  if (isImagePath(path)) {
    if (entry.uncompressedSize > MAX_IMAGE_PREVIEW_BYTES) {
      return {
        error: tooLargeToPreviewImageMessage,
        kind: "empty" as const,
      };
    }

    const blob = await runtime.readBinaryEntry({
      backend,
      path,
      unsupportedPreviewMessage,
      url,
    });
    return {
      blob,
      kind: "image" as const,
    };
  }

  return {
    kind: "empty" as const,
  };
};

export const getArchiveEntryDownload = async ({
  backend,
  entry,
  runtime,
  unsupportedPreviewMessage,
  url,
}: {
  backend: Exclude<ArchiveBackend, "none">;
  entry: ArchiveEntry;
  runtime: ArchiveViewerRuntime;
  unsupportedPreviewMessage: string;
  url: string;
}) => {
  const blob = await runtime.readBinaryEntry({
    backend,
    path: entry.path,
    unsupportedPreviewMessage,
    url,
  });

  return {
    blob,
    filename: entry.path.split("/").pop() || "download",
  };
};

const downloadBlob = (filename: string, blob: Blob) => {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
};

export const useArchiveViewerPreviewController = ({
  backend,
  runtime,
  selectedEntry,
  t,
  url,
}: {
  backend: ArchiveBackend;
  runtime: ArchiveViewerRuntime;
  selectedEntry: ArchiveEntry | null;
  t: (key: string) => string;
  url?: string;
}) => {
  const [previewKind, setPreviewKind] =
    useState<ArchiveViewerPreviewKind>("empty");
  const [previewText, setPreviewText] = useState("");
  const [previewImageUrl, setPreviewImageUrl] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const previewRequestIdRef = useRef(0);
  const previewImageUrlRef = useRef("");

  const replacePreviewImageUrl = useCallback((nextUrl: string) => {
    if (previewImageUrlRef.current) {
      URL.revokeObjectURL(previewImageUrlRef.current);
    }
    previewImageUrlRef.current = nextUrl;
    setPreviewImageUrl(nextUrl);
  }, []);

  const clearPreview = useCallback(() => {
    previewRequestIdRef.current += 1;
    setPreviewKind("empty");
    setPreviewText("");
    setPreviewError(null);
    setPreviewLoading(false);
    replacePreviewImageUrl("");
  }, [replacePreviewImageUrl]);

  const onDownloadSelected = useCallback(async () => {
    if (!selectedEntry || !url || backend === "none") return;
    try {
      const result = await getArchiveEntryDownload({
        backend,
        entry: selectedEntry,
        runtime,
        unsupportedPreviewMessage: t(
          "archive_viewer.errors.unsupported_preview_type",
        ),
        url,
      });
      downloadBlob(result.filename, result.blob);
    } catch {
      // handled by UI via preview errors; keep silent here
    }
  }, [backend, runtime, selectedEntry, t, url]);

  useEffect(() => {
    return () => {
      if (previewImageUrlRef.current) {
        URL.revokeObjectURL(previewImageUrlRef.current);
      }
    };
  }, []);

  useEffect(() => {
    clearPreview();
    if (!selectedEntry || !url || backend === "none") return;

    const requestId = previewRequestIdRef.current;

    const loadSelectedEntryPreview = async () => {
      setPreviewLoading(true);
      setPreviewError(null);
      try {
        const result = await loadArchiveEntryPreview({
          backend,
          entry: selectedEntry,
          runtime,
          tooLargeToPreviewImageMessage: t(
            "archive_viewer.errors.too_large_to_preview_image",
          ),
          tooLargeToPreviewTextMessage: t(
            "archive_viewer.errors.too_large_to_preview_text",
          ),
          unsupportedPreviewMessage: t(
            "archive_viewer.errors.unsupported_preview_type",
          ),
          url,
        });
        if (previewRequestIdRef.current !== requestId) return;

        if (result.kind === "text") {
          setPreviewKind("text");
          setPreviewText(result.text);
          return;
        }

        if (result.kind === "image") {
          const objectUrl = URL.createObjectURL(result.blob);
          if (previewRequestIdRef.current !== requestId) {
            URL.revokeObjectURL(objectUrl);
            return;
          }
          setPreviewKind("image");
          replacePreviewImageUrl(objectUrl);
          return;
        }

        setPreviewKind("empty");
        setPreviewError(result.error ?? null);
      } catch (error) {
        if (previewRequestIdRef.current !== requestId) return;
        setPreviewKind("empty");
        setPreviewError(
          error instanceof Error
            ? error.message
            : t("archive_viewer.errors.unknown"),
        );
      } finally {
        if (previewRequestIdRef.current !== requestId) return;
        setPreviewLoading(false);
      }
    };

    void loadSelectedEntryPreview();
  }, [backend, clearPreview, replacePreviewImageUrl, runtime, selectedEntry, t, url]);

  return {
    onDownloadSelected,
    previewError,
    previewImageUrl,
    previewKind,
    previewLoading,
    previewText,
  };
};
