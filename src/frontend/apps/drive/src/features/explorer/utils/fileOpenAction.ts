import type { Item } from "@/features/drivers/types";
import { openWopiInNewTab } from "@/features/ui/preview/wopi/openWopi";
import {
  getTextKey,
  isTextEligibleByRules,
  shouldUseWopiTextPreview,
} from "@/features/ui/preview/files-preview/previewRules";

type ExplorerFileOpenAction =
  | { type: "wopi-new-tab"; itemId: string }
  | { type: "preview" }
  | { type: "preview-unavailable" };

type ResolveExplorerFileOpenActionParams = {
  item: Pick<
    Item,
    "deleted_at" | "filename" | "id" | "is_wopi_supported" | "mimetype" | "title" | "url"
  >;
  requirePreviewUrl?: boolean;
};

type OpenFileFromExplorerParams = ResolveExplorerFileOpenActionParams & {
  item: Item;
  openPreview: (item: Item) => void;
  onPreviewUnavailable?: () => void;
  openWopi?: (itemId: string) => void;
};

export const resolveExplorerFileOpenAction = ({
  item,
  requirePreviewUrl = false,
}: ResolveExplorerFileOpenActionParams): ExplorerFileOpenAction => {
  const filename = item.filename || item.title || "";
  const useTextPreview =
    getTextKey(filename) !== null &&
    isTextEligibleByRules(item.mimetype ?? "", filename) &&
    !shouldUseWopiTextPreview(filename);

  if (item.is_wopi_supported && !item.deleted_at && !useTextPreview) {
    return { type: "wopi-new-tab", itemId: item.id };
  }

  if (requirePreviewUrl && !item.url) {
    return { type: "preview-unavailable" };
  }

  return { type: "preview" };
};

export const openFileFromExplorer = ({
  item,
  openPreview,
  onPreviewUnavailable,
  openWopi = openWopiInNewTab,
  requirePreviewUrl = false,
}: OpenFileFromExplorerParams) => {
  const action = resolveExplorerFileOpenAction({
    item,
    requirePreviewUrl,
  });

  if (action.type === "wopi-new-tab") {
    openWopi(action.itemId);
    return;
  }

  if (action.type === "preview-unavailable") {
    onPreviewUnavailable?.();
    return;
  }

  openPreview(item);
};
