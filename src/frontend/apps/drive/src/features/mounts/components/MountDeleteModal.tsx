import React from "react";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { getDriver } from "@/features/config/Config";
import { errorToString } from "@/features/api/APIError";
import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";
import { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import {
  getMountBulkSelectionState,
  sortMountItemsForDelete,
} from "@/features/mounts/utils/mountBulkActions";

export const MountDeleteModal = (
  props: Pick<ModalProps, "isOpen" | "onClose"> & {
    items: MountExplorerItem[];
    onSuccess: (payload: {
      deletedItems: MountExplorerItem[];
      partialFailure?: {
        item: MountExplorerItem;
        completedCount: number;
        error: unknown;
      };
    }) => void;
  },
) => {
  const { t } = useTranslation();
  const primaryItem = props.items[0];
  const selection = getMountBulkSelectionState(props.items);
  const isFolder = props.items.length === 1 && primaryItem?.mountMeta.entryType === "folder";
  const isMultiple = props.items.length > 1;

  const handleDelete = async () => {
    if (!selection.sameMount || !selection.canDelete) {
      addToast(
        <ToasterItem type="error">
          {t(
            selection.sameMount
              ? "explorer.mounts.bulk.delete.unsupported_selection"
              : "explorer.mounts.bulk.delete.mixed_mount",
          )}
        </ToasterItem>,
      );
      return;
    }

    const deletedItems: MountExplorerItem[] = [];
    try {
      for (const item of sortMountItemsForDelete(props.items)) {
        await getDriver().deleteMountEntry({
          mountId: item.mountMeta.mountId,
          path: item.mountMeta.normalizedPath,
        });
        deletedItems.push(item);
      }
      addToast(
        <ToasterItem>
          <span className="material-icons">delete</span>
          <span>{t("explorer.actions.delete.toast", { count: props.items.length })}</span>
        </ToasterItem>,
      );
      props.onSuccess({ deletedItems });
      props.onClose();
    } catch (error) {
      if (deletedItems.length > 0) {
        addToast(
          <ToasterItem>
            <span className="material-icons">delete</span>
            <span>{t("explorer.actions.delete.toast", { count: deletedItems.length })}</span>
          </ToasterItem>,
        );
      }
      const failedItem = sortMountItemsForDelete(props.items)[deletedItems.length] ?? primaryItem;
      addToast(
        <ToasterItem type="error">
          {t("explorer.mounts.bulk.delete.partial_error", {
            count: deletedItems.length,
            name: failedItem?.title ?? "",
            detail: errorToString(error),
          })}
        </ToasterItem>,
      );
      props.onSuccess({
        deletedItems,
        partialFailure: {
          item: failedItem!,
          completedCount: deletedItems.length,
          error,
        },
      });
      props.onClose();
    }
  };

  if (!primaryItem) {
    return null;
  }

  return (
    <Modal
      {...props}
      size={ModalSize.SMALL}
      title={t(
        isMultiple
          ? "explorer.mounts.bulk.delete.modal.title_multiple"
          : isFolder
          ? "explorer.mounts.crud.delete.modal.title_folder"
          : "explorer.mounts.crud.delete.modal.title_file",
      )}
      rightActions={
        <>
          <Button variant="bordered" onClick={props.onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => void handleDelete()}>
            {t("explorer.item.actions.delete")}
          </Button>
        </>
      }
    >
      <div className="mt-s">
        {t(
          isMultiple
            ? "explorer.mounts.bulk.delete.modal.description_multiple"
            : isFolder
            ? "explorer.mounts.crud.delete.modal.description_folder"
            : "explorer.mounts.crud.delete.modal.description_file",
          {
            name: primaryItem.title,
            count: props.items.length,
          },
        )}
      </div>
    </Modal>
  );
};
