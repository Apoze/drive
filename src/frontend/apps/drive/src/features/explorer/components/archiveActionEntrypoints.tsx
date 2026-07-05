import React from "react";
import { Item, ItemType } from "@/features/drivers/types";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";

type Translate = (key: string, options?: Record<string, unknown>) => string;

type ArchiveEligibilityItem = Pick<Item, "abilities" | "filename" | "title" | "type">;

export const canZipSelection = (
  items: Array<Pick<Item, "abilities">>,
) => items.length > 0 && items.every((item) => item.abilities?.retrieve);

export const isZipArchiveItem = (item: ArchiveEligibilityItem) =>
  item.type === ItemType.FILE &&
  (item.filename || item.title || "").toLowerCase().endsWith(".zip");

export const canUnzipItem = (
  item: ArchiveEligibilityItem,
  options?: { minimal?: boolean },
) => !options?.minimal && Boolean(item.abilities?.retrieve) && isZipArchiveItem(item);

export const showArchiveZipLowRightsToast = (t: Translate) => {
  addToast(
    <ToasterItem type="error">
      <span className="material-icons">archive</span>
      <span>{t("explorer.actions.archive.zip.low_rights_toast")}</span>
    </ToasterItem>,
  );
};

export const openArchiveItemModal = <TItem,>({
  item,
  openModal,
  setCurrentItem,
}: {
  item: TItem;
  openModal: () => void;
  setCurrentItem: (item: TItem) => void;
}) => {
  setCurrentItem(item);
  openModal();
};
