import type { Item } from "@/features/drivers/types";
import { openWopiInNewTab } from "@/features/ui/preview/wopi/openWopi";

type ExplorerFileOpenAction =
  | { type: "wopi-new-tab"; itemId: string }
  | { type: "preview" }
  | { type: "preview-unavailable" };

type ResolveExplorerFileOpenActionParams = {
  item: Pick<Item, "deleted_at" | "id" | "is_wopi_supported" | "url">;
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
  if (item.is_wopi_supported && !item.deleted_at) {
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
