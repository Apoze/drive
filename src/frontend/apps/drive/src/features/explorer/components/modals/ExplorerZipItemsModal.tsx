import React from "react";
import { Item } from "@/features/drivers/types";
import { useStartArchiveZip } from "@/features/explorer/api/useArchiveZip";
import { RhfInput } from "@/features/forms/components/RhfInput";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { FormProvider, SubmitHandler, useForm } from "react-hook-form";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ExplorerPickFolderModal } from "./ExplorerPickFolderModal";
import {
  createArchiveZipSubmitController,
  defaultArchiveNameForItems,
} from "./archiveActionSubmitControllers";
import { useArchiveDestinationController } from "./useArchiveDestinationController";

type Inputs = {
  archive_name: string;
};

export const ExplorerZipItemsModal = (
  props: Pick<ModalProps, "isOpen" | "onClose"> & {
    items: Item[];
    initialDestinationFolderId?: string;
  },
) => {
  const { t } = useTranslation();
  const startZip = useStartArchiveZip();
  const destinationController = useArchiveDestinationController({
    initialDestinationFolderId: props.initialDestinationFolderId,
    isOpen: props.isOpen,
  });

  const form = useForm<Inputs>({
    defaultValues: {
      archive_name: defaultArchiveNameForItems(props.items),
    },
  });

  useEffect(() => {
    if (!props.isOpen) {
      return;
    }
    form.reset({
      archive_name: defaultArchiveNameForItems(props.items),
    });
  }, [form, props.initialDestinationFolderId, props.isOpen, props.items]);
  const { destinationLabel, effectiveDestinationId, pickFolderModal } =
    destinationController;
  const zipSubmitController = createArchiveZipSubmitController({
    destinationFolderId: effectiveDestinationId,
    itemIds: props.items.map((item) => item.id),
    onClose: props.onClose,
    startZip,
    t,
  });

  const canSubmit = Boolean(effectiveDestinationId) && !startZip.isPending;

  const onSubmit: SubmitHandler<Inputs> = async (data) => {
    await zipSubmitController.submitArchiveZip(data.archive_name);
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
          {...destinationController.pickFolderModalProps}
        />
      )}
    </>
  );
};
