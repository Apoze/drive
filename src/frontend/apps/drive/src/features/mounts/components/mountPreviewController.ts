import {
  getMountExplorerMeta,
  type MountExplorerItem,
} from "@/features/mounts/utils/mountExplorerItems";
import { createPreviewCurrentItemController } from "@/features/ui/preview/files-preview/previewCurrentItemController";

type MountPreviewControllerParams = {
  previewItem?: MountExplorerItem;
  setPreviewCurrentItem: (item?: MountExplorerItem) => void;
};

export const createMountPreviewController = ({
  previewItem,
  setPreviewCurrentItem,
}: MountPreviewControllerParams) => {
  const previewCurrentItemController =
    createPreviewCurrentItemController<MountExplorerItem>({
      previewItem,
      setPreviewCurrentItem,
    });

  const openPreview = (item: MountExplorerItem) => {
    if (!getMountExplorerMeta(item).abilities?.preview) {
      return;
    }

    previewCurrentItemController.setPreviewCurrentItem(item);
  };

  const closePreviewIfCurrent = (itemId: string) => {
    previewCurrentItemController.closePreviewIf((currentPreviewItem) =>
      currentPreviewItem.id === itemId,
    );
  };

  const closePreviewIfIncluded = (items: MountExplorerItem[]) => {
    previewCurrentItemController.closePreviewIf((currentPreviewItem) =>
      items.some((item) => item.id === currentPreviewItem.id),
    );
  };

  return {
    ...previewCurrentItemController,
    openPreview,
    closePreviewIfCurrent,
    closePreviewIfIncluded,
  };
};

export type MountPreviewController = ReturnType<
  typeof createMountPreviewController
>;
