import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MimeCategory } from "@/features/explorer/utils/mimeTypes";
import { getPreviewMimeCategory } from "./previewRules";
import {
  FilePreviewType,
  PreviewSource,
  getResolvePreviewQueryKey,
} from "./previewSource";

const STREAM_URL_REUSE_GRACE_MS = 30 * 1000;

const hasFreshResolvedStreamUrl = (
  value: Partial<FilePreviewType> | null | undefined,
) => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const expiresAt = (value as { stream_expires_at?: number | null }).stream_expires_at;
  if (typeof expiresAt !== "number") {
    return false;
  }
  return expiresAt - Date.now() > STREAM_URL_REUSE_GRACE_MS;
};

type PreviewFileWithCategory = FilePreviewType & {
  category: MimeCategory;
};

export const useResolvedPreviewFile = <T extends PreviewFileWithCategory>(
  currentFile: T | undefined,
  source: PreviewSource,
) => {
  const queryClient = useQueryClient();

  const resolvedPreviewQueryKey = currentFile
    ? getResolvePreviewQueryKey(source, currentFile)
    : ["file-preview", undefined, "resolved"];

  const cachedResolvedPreview = currentFile
    ? (queryClient.getQueryData(resolvedPreviewQueryKey) as
        | Partial<FilePreviewType>
        | null
        | undefined)
    : null;
  const canReuseCachedResolvedPreview = hasFreshResolvedStreamUrl(
    cachedResolvedPreview,
  );

  const resolvedPreviewQuery = useQuery({
    queryKey: resolvedPreviewQueryKey,
    enabled: Boolean(
      currentFile && source.resolveFilePreview && !canReuseCachedResolvedPreview,
    ),
    refetchOnWindowFocus: false,
    retry: false,
    queryFn: async () => {
      if (!currentFile || !source.resolveFilePreview) {
        return null;
      }
      return source.resolveFilePreview(currentFile);
    },
  });

  const resolved = canReuseCachedResolvedPreview
    ? cachedResolvedPreview
    : resolvedPreviewQuery.data;

  const effectiveCurrentFile = currentFile
    ? (() => {
        if (!resolved) {
          return currentFile;
        }
        const filename =
          resolved.filename ?? currentFile.filename ?? currentFile.title ?? "";
        let category = currentFile.category;
        switch (resolved.preview_kind) {
          case "image":
            category = MimeCategory.IMAGE;
            break;
          case "video":
            category = MimeCategory.VIDEO;
            break;
          case "audio":
            category = MimeCategory.AUDIO;
            break;
          case "pdf":
            category = MimeCategory.PDF;
            break;
          case "archive":
            category = MimeCategory.ARCHIVE;
            break;
          default:
            category = getPreviewMimeCategory(
              resolved.mimetype ?? currentFile.mimetype,
              filename,
            );
            break;
        }
        return {
          ...currentFile,
          ...resolved,
          category,
        } as T;
      })()
    : undefined;

  const isResolvingCurrentFile = Boolean(
    currentFile &&
      source.resolveFilePreview &&
      resolvedPreviewQuery.isLoading &&
      !canReuseCachedResolvedPreview &&
      !resolvedPreviewQuery.data,
  );

  return {
    effectiveCurrentFile,
    isResolvingCurrentFile,
    resolvedPreviewQuery,
  };
};
