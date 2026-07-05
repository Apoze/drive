import React from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getDriver } from "@/features/config/Config";
import { errorToString } from "@/features/api/APIError";
import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";
import {
  MountExplorerItem,
  getMountTitle,
} from "@/features/mounts/utils/mountExplorerItems";
import { MountVirtualEntry } from "@/features/drivers/types";
import {
  getMountBulkSelectionState,
  getParentMountPath,
} from "@/features/mounts/utils/mountBulkActions";
import { resolveMountMoveModalState } from "./mountMutationModalHelpers";

export const MountMoveModal = (
  props: Pick<ModalProps, "isOpen" | "onClose"> & {
    items: MountExplorerItem[];
    initialDestinationPath: string;
    onSuccess: (payload: {
      sourceItems: MountExplorerItem[];
      movedEntries: MountVirtualEntry[];
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
  const selection = useMemo(
    () => getMountBulkSelectionState(props.items),
    [props.items],
  );
  const [currentPath, setCurrentPath] = useState(props.initialDestinationPath || "/");

  useEffect(() => {
    if (props.isOpen) {
      setCurrentPath(props.initialDestinationPath || "/");
    }
  }, [props.initialDestinationPath, props.isOpen]);

  const browseQuery = useQuery({
    queryKey: ["mounts", "move-modal", primaryItem?.mountMeta.mountId, currentPath],
    enabled: props.isOpen && Boolean(primaryItem?.mountMeta.mountId) && selection.sameMount,
    refetchOnWindowFocus: false,
    queryFn: () =>
      getDriver().browseMount({
        mountId: primaryItem.mountMeta.mountId,
        path: currentPath,
      }),
  });

  const { childFolders, movePreflightError, canSubmit } = useMemo(
    () =>
      resolveMountMoveModalState({
        items: props.items,
        currentPath,
        destinationEntries: browseQuery.data?.children?.results,
        isLoading: browseQuery.isLoading,
        isError: browseQuery.isError,
      }),
    [
      browseQuery.data?.children?.results,
      browseQuery.isError,
      browseQuery.isLoading,
      currentPath,
      props.items,
    ],
  );

  const handleMove = async () => {
    if (!primaryItem) {
      return;
    }
    if (movePreflightError) {
      addToast(
        <ToasterItem type="error">
          {t(`explorer.mounts.bulk.move.${movePreflightError.code}`)}
        </ToasterItem>,
      );
      return;
    }

    const movedEntries: MountVirtualEntry[] = [];
    try {
      for (const item of props.items) {
        const entry = await getDriver().moveMountEntry({
          mountId: item.mountMeta.mountId,
          path: item.mountMeta.normalizedPath,
          targetPath: currentPath,
        });
        movedEntries.push(entry);
      }
      addToast(
        <ToasterItem>
          {t("explorer.actions.move.toast", { count: props.items.length })}
        </ToasterItem>,
      );
      props.onSuccess({ sourceItems: props.items, movedEntries });
      props.onClose();
    } catch (error) {
      if (movedEntries.length > 0) {
        addToast(
          <ToasterItem>
            {t("explorer.actions.move.toast", { count: movedEntries.length })}
          </ToasterItem>,
        );
      }
      const failedItem = props.items[movedEntries.length] ?? props.items[0];
      addToast(
        <ToasterItem type="error">
          {t("explorer.mounts.bulk.move.partial_error", {
            count: movedEntries.length,
            name: failedItem?.title ?? "",
            detail: errorToString(error),
          })}
        </ToasterItem>,
      );
      props.onSuccess({
        sourceItems: props.items,
        movedEntries,
        partialFailure: {
          item: failedItem,
          completedCount: movedEntries.length,
          error,
        },
      });
      props.onClose();
    }
  };

  if (!primaryItem) {
    return null;
  }

  const mountTitle = getMountTitle({
    provider: primaryItem.mountMeta.provider ?? "mount",
    display_name: primaryItem.mountMeta.mountTitle,
  });
  const parentPath = getParentMountPath(currentPath);
  const isMultiple = props.items.length > 1;

  return (
    <Modal
      {...props}
      size={ModalSize.MEDIUM}
      title={t("explorer.mounts.crud.move.modal.title")}
      rightActions={
        <>
          <Button variant="bordered" onClick={props.onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => void handleMove()} disabled={!canSubmit}>
            {t("explorer.item.actions.move")}
          </Button>
        </>
      }
    >
      <div className="mt-s">
        {t(
          isMultiple
            ? "explorer.mounts.bulk.move.modal.description_multiple"
            : "explorer.mounts.crud.move.modal.description",
          {
            count: props.items.length,
            name: primaryItem.title,
          },
        )}
      </div>
      <div className="mt-s">
        <strong>{t("explorer.mounts.crud.move.modal.destination_label")}</strong>
        <div>{`${mountTitle}${currentPath}`}</div>
      </div>
      {parentPath !== null && (
        <div className="mt-s">
          <Button variant="tertiary" size="small" onClick={() => setCurrentPath(parentPath)}>
            {t("explorer.mounts.crud.move.modal.parent_folder")}
          </Button>
        </div>
      )}
      <div className="mt-s">
        {browseQuery.isLoading && <div>{t("explorer.mounts.browse_loading")}</div>}
        {browseQuery.isError && <div>{t("explorer.mounts.browse_error")}</div>}
        {!browseQuery.isLoading && !browseQuery.isError && childFolders.length === 0 && (
          <div>{t("explorer.mounts.children.empty")}</div>
        )}
        {!browseQuery.isLoading && !browseQuery.isError && movePreflightError && (
          <div className="text-danger-500 mt-2">
            {t(`explorer.mounts.bulk.move.${movePreflightError.code}`, {
              name: movePreflightError.conflictingName,
            })}
          </div>
        )}
        {!browseQuery.isLoading && !browseQuery.isError && childFolders.length > 0 && (
          <div className="flex flex-col gap-2">
            {childFolders.map((folder) => (
              <Button
                key={folder.normalized_path}
                variant="tertiary"
                onClick={() => setCurrentPath(folder.normalized_path)}
              >
                {folder.name}
              </Button>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
};
