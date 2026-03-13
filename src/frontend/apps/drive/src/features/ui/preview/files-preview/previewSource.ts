import { getDriver } from "@/features/config/Config";
import { APIError } from "@/features/api/APIError";
import { ItemTextContent } from "@/features/drivers/types";
import type { ReactNode } from "react";

export type FilePreviewType = {
  id: string;
  size: number;
  title: string;
  filename?: string;
  mimetype: string;
  is_wopi_supported?: boolean;
  url_preview?: string;
  url?: string;
  stream_url?: string;
  stream_expires_at?: number;
  can_update?: boolean;
  preview_kind?:
    | "image"
    | "video"
    | "audio"
    | "pdf"
    | "text"
    | "archive"
    | "wopi"
    | "unsupported";
};

export type PreviewResolveResult = Partial<FilePreviewType> | null;

export interface PreviewSource {
  fetchTextContent?: (file: FilePreviewType) => Promise<ItemTextContent | null>;
  getTextQueryKey?: (
    file: FilePreviewType,
  ) => (string | number | null | undefined)[];
  saveTextContent?: (params: {
    file: FilePreviewType;
    content: string;
    etag: string;
  }) => Promise<{ etag: string | null }>;
  resolveFilePreview?: (file: FilePreviewType) => Promise<PreviewResolveResult>;
  getResolveFilePreviewQueryKey?: (
    file: FilePreviewType,
  ) => (string | number | null | undefined)[];
  renderWopiEditor?: (
    file: FilePreviewType,
    onFileRename?: (file: FilePreviewType, newName: string) => void,
  ) => ReactNode;
  renderArchiveViewer?: (
    file: FilePreviewType,
    onDownload?: () => void,
  ) => ReactNode;
}

const defaultTextQueryKey = (file: FilePreviewType) => ["item", file.id, "text"];
const defaultResolvePreviewQueryKey = (file: FilePreviewType) => [
  "file-preview",
  file.id,
  "resolved",
];

export const defaultPreviewSource: PreviewSource = {
  async fetchTextContent(file) {
    try {
      return await getDriver().getItemText(file.id);
    } catch (err) {
      if (err instanceof APIError && (err.code === 400 || err.code === 415)) {
        return null;
      }
      throw err;
    }
  },
  getTextQueryKey: defaultTextQueryKey,
  saveTextContent({ file, content, etag }) {
    return getDriver().saveItemText({
      itemId: file.id,
      content,
      etag,
    });
  },
  getResolveFilePreviewQueryKey: defaultResolvePreviewQueryKey,
};

export const getTextPreviewQueryKey = (
  source: PreviewSource,
  file: FilePreviewType,
) => source.getTextQueryKey?.(file) ?? defaultTextQueryKey(file);

export const getResolvePreviewQueryKey = (
  source: PreviewSource,
  file: FilePreviewType,
) => source.getResolveFilePreviewQueryKey?.(file) ?? defaultResolvePreviewQueryKey(file);
