import { MimeCategory } from "@/features/explorer/utils/mimeTypes";
import type { FilePreviewType } from "./previewSource";

export type PreviewViewerKind =
  | "empty"
  | "suspicious"
  | "resolving"
  | "resolve_error"
  | "unsupported_kind"
  | "text"
  | "wopi"
  | "missing_url"
  | "image"
  | "unsupported_heic"
  | "video"
  | "audio"
  | "pdf"
  | "archive"
  | "unsupported";

type PreviewViewerStateInput = {
  currentFile?: {
    isSuspicious?: boolean;
  };
  effectiveCurrentFile?: (FilePreviewType & {
    category: MimeCategory;
  }) | undefined;
  isResolvingCurrentFile: boolean;
  hasResolveError: boolean;
  useTextViewer: boolean;
  shouldRenderWopi: boolean;
};

export const resolvePreviewViewerKind = ({
  currentFile,
  effectiveCurrentFile,
  isResolvingCurrentFile,
  hasResolveError,
  useTextViewer,
  shouldRenderWopi,
}: PreviewViewerStateInput): PreviewViewerKind => {
  if (!currentFile || !effectiveCurrentFile) {
    return "empty";
  }
  if (currentFile.isSuspicious) {
    return "suspicious";
  }
  if (isResolvingCurrentFile) {
    return "resolving";
  }
  if (hasResolveError) {
    return "resolve_error";
  }
  if (effectiveCurrentFile.preview_kind === "unsupported") {
    return "unsupported_kind";
  }
  if (useTextViewer) {
    return "text";
  }
  if (shouldRenderWopi) {
    return "wopi";
  }
  if (
    !effectiveCurrentFile.url_preview &&
    effectiveCurrentFile.category !== MimeCategory.ARCHIVE
  ) {
    return "missing_url";
  }

  switch (effectiveCurrentFile.category) {
    case MimeCategory.IMAGE:
      return effectiveCurrentFile.mimetype.includes("heic")
        ? "unsupported_heic"
        : "image";
    case MimeCategory.VIDEO:
      return "video";
    case MimeCategory.AUDIO:
      return "audio";
    case MimeCategory.PDF:
      return "pdf";
    case MimeCategory.ARCHIVE:
      return "archive";
    default:
      return "unsupported";
  }
};
