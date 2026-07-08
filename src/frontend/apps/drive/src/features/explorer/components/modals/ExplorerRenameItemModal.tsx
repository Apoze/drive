import React from "react";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { FormProvider, SubmitHandler, useForm } from "react-hook-form";
import { Item } from "@/features/drivers/types";
import { RhfInput } from "@/features/forms/components/RhfInput";
import { useMutationRenameItem } from "../../hooks/useMutations";
import { useRef } from "react";
import { useTreeUtils } from "../../hooks/useTreeUtils";
import { useGlobalExplorer } from "../GlobalExplorerContext";
import {
  buildNextRenamedRightPanelItem,
  getRenameInputTitle,
  getRenameMutationTitle,
} from "./itemMutationModalHelpers";
import { useSelectionStore } from "@/features/explorer/stores/selectionStore";

type Inputs = {
  title: string;
};

export const ExplorerRenameItemModal = (
  props: Pick<ModalProps, "isOpen" | "onClose"> & {
    item: Item;
  },
) => {
  const treeUtils = useTreeUtils();
  const {
    rightPanelForcedItem,
    replaceRightPanelItem,
  } = useGlobalExplorer();
  const selectionStore = useSelectionStore();
  const { t } = useTranslation();
  const form = useForm<Inputs>({
    defaultValues: {
      title: getRenameInputTitle(props.item),
    },
  });

  const updateItem = useMutationRenameItem();
  const initialRightPanelItemRef = useRef(
    rightPanelForcedItem ?? selectionStore.getSelectedItems()[0],
  );

  const onSubmit: SubmitHandler<Inputs> = async (data) => {
    const title = getRenameMutationTitle({
      item: props.item,
      title: data.title,
    });
    let nextRightPanelForcedItem: Item | undefined;

    await updateItem.mutateAsync(
      {
        ...data,
        title,
        id: props.item.id,
      },
      {
        onSuccess: (_, updatedItem) => {
          treeUtils.updateNodeByOriginalId(props.item.id, {
            title,
          });

          nextRightPanelForcedItem = buildNextRenamedRightPanelItem({
            currentItem: initialRightPanelItemRef.current,
            fallbackItem: props.item,
            updatedItem,
            title,
          });
        },
      },
    );

    props.onClose();

    if (nextRightPanelForcedItem) {
      replaceRightPanelItem(nextRightPanelForcedItem);
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
          <Button type="submit" form="rename-item-form">
            {t("explorer.actions.rename.modal.submit")}
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          id="rename-item-form"
          className="mt-s"
        >
          <RhfInput
            label={t("explorer.actions.rename.modal.label")}
            type="text"
            {...inputRegister}
            ref={(e) => {
              inputRegister.ref(e);
              if (!inputRef.current) {
                e?.focus();
                e?.setSelectionRange(0, e.value.length);
                // We only set the ref once because it sometimes call this function with e === null, don't know why,
                // but it causes setSelectionRange to be called frenetically.
                inputRef.current = e;
              }
            }}
          />
        </form>
      </FormProvider>
    </Modal>
  );
};
