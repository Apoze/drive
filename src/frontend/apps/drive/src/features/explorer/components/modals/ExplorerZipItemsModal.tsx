import { Item, ItemType } from "@/features/drivers/types";
import { errorToString } from "@/features/api/APIError";
import { useStartArchiveZip } from "@/features/explorer/api/useArchiveZip";
import { showArchiveJobToast } from "@/features/explorer/components/toasts/ArchiveJobToast";
import { useItem } from "@/features/explorer/hooks/useQueries";
import { RhfInput } from "@/features/forms/components/RhfInput";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
  useModal,
} from "@gouvfr-lasuite/cunningham-react";
import { FormProvider, SubmitHandler, useForm } from "react-hook-form";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";
import { ExplorerPickFolderModal } from "./ExplorerPickFolderModal";

type Inputs = {
  archive_name: string;
};

const ensureZipSuffix = (name: string) => {
  const trimmed = (name || "").trim();
  if (!trimmed) return "archive.zip";
  return trimmed.toLowerCase().endsWith(".zip") ? trimmed : `${trimmed}.zip`;
};

const defaultArchiveNameForItems = (items: Item[]) => {
  if (items.length === 1) {
    const item = items[0];
    if (item.type === ItemType.FOLDER) {
      return ensureZipSuffix(item.title);
    }
    const base = (item.filename || item.title || "").replace(/\.[^/.]+$/, "");
    return ensureZipSuffix(base || "archive");
  }
  return "archive.zip";
};

export const ExplorerZipItemsModal = (
  props: Pick<ModalProps, "isOpen" | "onClose"> & {
    items: Item[];
    initialDestinationFolderId?: string;
  },
) => {
  const { t } = useTranslation();
  const startZip = useStartArchiveZip();
  const pickFolderModal = useModal();

  const form = useForm<Inputs>({
    defaultValues: {
      archive_name: defaultArchiveNameForItems(props.items),
    },
  });

  const [destinationFolderId, setDestinationFolderId] = useState<string | undefined>(
    props.initialDestinationFolderId,
  );

  useEffect(() => {
    if (!props.isOpen) {
      return;
    }
    setDestinationFolderId(props.initialDestinationFolderId);
    form.reset({
      archive_name: defaultArchiveNameForItems(props.items),
    });
  }, [form, props.initialDestinationFolderId, props.isOpen, props.items]);

  const effectiveDestinationId = destinationFolderId;
  const destinationItem = useItem(effectiveDestinationId || "", {
    enabled: !!effectiveDestinationId,
  });

  const destinationLabel = useMemo(() => {
    if (!effectiveDestinationId) {
      return t("explorer.actions.archive.common.destination_unknown");
    }
    return destinationItem.data?.title || t("explorer.actions.archive.common.destination_loading");
  }, [destinationItem.data?.title, effectiveDestinationId, t]);

  const canSubmit = Boolean(effectiveDestinationId) && !startZip.isPending;

  const onSubmit: SubmitHandler<Inputs> = async (data) => {
    if (!effectiveDestinationId) {
      return;
    }

    try {
      const res = await startZip.mutateAsync({
        item_ids: props.items.map((i) => i.id),
        destination_folder_id: effectiveDestinationId,
        archive_name: ensureZipSuffix(data.archive_name),
      });

      showArchiveJobToast({
        kind: "zip",
        jobId: res.job_id,
        destinationFolderId: effectiveDestinationId,
      });

      props.onClose();
    } catch (e) {
      addToast(
        <ToasterItem type="error">
          <span className="material-icons">archive</span>
          <span>
            {errorToString(e) || t("explorer.actions.archive.zip.toast_failed")}
          </span>
        </ToasterItem>,
      );
    }
  };

  return (
    <>
      <Modal
        {...props}
        size={ModalSize.SMALL}
        title={t("explorer.actions.archive.zip.modal.title")}
        rightActions={
          <>
            <Button variant="bordered" onClick={props.onClose}>
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              form="explorer-zip-items-form"
              disabled={!canSubmit}
            >
              {t("explorer.actions.archive.zip.modal.submit")}
            </Button>
          </>
        }
      >
        <FormProvider {...form}>
          <form
            id="explorer-zip-items-form"
            onSubmit={form.handleSubmit(onSubmit)}
            className="mt-s"
          >
            <RhfInput
              name="archive_name"
              label={t("explorer.actions.archive.zip.modal.archive_name_label")}
              type="text"
            />

            <div className="mt-s">
              <div style={{ marginBottom: 8, fontWeight: 600 }}>
                {t("explorer.actions.archive.common.destination_label")}
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <div style={{ flex: 1 }}>{destinationLabel}</div>
                <Button
                  size="small"
                  variant="tertiary"
                  onClick={pickFolderModal.open}
                  type="button"
                >
                  {t("explorer.actions.archive.common.change_destination")}
                </Button>
              </div>
            </div>
          </form>
        </FormProvider>
      </Modal>

      {pickFolderModal.isOpen && (
        <ExplorerPickFolderModal
          {...pickFolderModal}
          initialFolderId={effectiveDestinationId}
          onPick={(folderId) => setDestinationFolderId(folderId)}
        />
      )}
    </>
  );
};
