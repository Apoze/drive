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
import {
  preserveKnownExtensionOnRename,
  removeFileExtension,
} from "@/features/explorer/utils/mimeTypes";
import { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { ItemType, MountVirtualEntry } from "@/features/drivers/types";

type Inputs = {
  title: string;
};

export const MountRenameModal = (
  props: Pick<ModalProps, "isOpen" | "onClose"> & {
    item: MountExplorerItem;
    onSuccess: (entry: MountVirtualEntry) => void;
  },
) => {
  const { t } = useTranslation();
  const form = useForm<Inputs>({
    defaultValues: {
      title:
        props.item.type === ItemType.FILE
          ? removeFileExtension(props.item.title)
          : props.item.title,
    },
  });

  const onSubmit: SubmitHandler<Inputs> = async (data) => {
    const name =
      props.item.type === ItemType.FILE
        ? preserveKnownExtensionOnRename(props.item.title, data.title)
        : data.title;

    try {
      const entry = await getDriver().renameMountEntry({
        mountId: props.item.mountMeta.mountId,
        path: props.item.mountMeta.normalizedPath,
        name,
      });
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
      title={t("explorer.actions.rename.modal.title")}
      rightActions={
        <>
          <Button variant="bordered" onClick={props.onClose}>
            {t("explorer.actions.rename.modal.cancel")}
          </Button>
          <Button type="submit" form="rename-mount-form">
            {t("explorer.actions.rename.modal.submit")}
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          id="rename-mount-form"
          className="mt-s"
        >
          <RhfInput
            label={t("explorer.actions.rename.modal.label")}
            type="text"
            {...inputRegister}
            ref={(element) => {
              inputRegister.ref(element);
              if (!inputRef.current) {
                element?.focus();
                element?.setSelectionRange(0, element.value.length);
                inputRef.current = element;
              }
            }}
          />
        </form>
      </FormProvider>
    </Modal>
  );
};
