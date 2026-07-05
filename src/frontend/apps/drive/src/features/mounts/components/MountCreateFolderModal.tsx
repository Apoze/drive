import React from "react";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { FormProvider, SubmitHandler, useForm } from "react-hook-form";
import { useRef } from "react";
import { RhfInput } from "@/features/forms/components/RhfInput";
import { getDriver } from "@/features/config/Config";
import { errorToString } from "@/features/api/APIError";
import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";
import { MountVirtualEntry } from "@/features/drivers/types";

type Inputs = {
  title: string;
};

export const MountCreateFolderModal = (
  props: Pick<ModalProps, "isOpen" | "onClose"> & {
    mountId: string;
    parentPath: string;
    onSuccess: (entry: MountVirtualEntry) => void;
  },
) => {
  const { t } = useTranslation();
  const form = useForm<Inputs>();

  const onSubmit: SubmitHandler<Inputs> = async (data) => {
    try {
      const entry = await getDriver().createMountFolder({
        mountId: props.mountId,
        path: props.parentPath,
        name: data.title,
      });
      addToast(
        <ToasterItem>{t("explorer.mounts.create_folder.success")}</ToasterItem>,
      );
      form.reset();
      props.onSuccess(entry);
      props.onClose();
    } catch (error) {
      addToast(<ToasterItem type="error">{errorToString(error)}</ToasterItem>);
    }
  };

  const inputRef = useRef<HTMLInputElement>(null);
  const inputRegister = form.register("title");

  return (
    <Modal
      {...props}
      size={ModalSize.SMALL}
      title={t("explorer.actions.createFolder.modal.title")}
      rightActions={
        <>
          <Button variant="bordered" onClick={props.onClose}>
            {t("explorer.actions.createFolder.modal.cancel")}
          </Button>
          <Button type="submit" form="create-mount-folder-form">
            {t("explorer.actions.createFolder.modal.submit")}
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          id="create-mount-folder-form"
          className="mt-s"
        >
          <RhfInput
            label={t("explorer.actions.createFolder.modal.label")}
            type="text"
            {...inputRegister}
            ref={(element) => {
              inputRegister.ref(element);
              if (!inputRef.current) {
                element?.focus();
                inputRef.current = element;
              }
            }}
          />
        </form>
      </FormProvider>
    </Modal>
  );
};
