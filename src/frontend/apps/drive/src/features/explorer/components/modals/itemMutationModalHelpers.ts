import { Item, ItemType } from "@/features/drivers/types";
import {
  preserveKnownExtensionOnRename,
  removeFileExtension,
} from "../../utils/mimeTypes";

export type CreateFileKind = "text" | "sheet" | "slide";

export type CreateFileExtensionOption = {
  ext: string;
  labelKey: string;
  isRecommended?: boolean;
};

export const DEFAULT_CREATE_FILE_EXTENSION_BY_KIND: Record<
  CreateFileKind,
  string
> = {
  text: "odt",
  sheet: "ods",
  slide: "odp",
};

export const CREATE_FILE_EXTENSIONS_BY_KIND: Record<
  CreateFileKind,
  CreateFileExtensionOption[]
> = {
  text: [
    { ext: "odt", labelKey: "odt", isRecommended: true },
    { ext: "docx", labelKey: "docx" },
    { ext: "doc", labelKey: "doc" },
    { ext: "rtf", labelKey: "rtf" },
    { ext: "txt", labelKey: "txt" },
    { ext: "md", labelKey: "md" },
    { ext: "sh", labelKey: "sh" },
    { ext: "ps1", labelKey: "ps1" },
  ],
  sheet: [
    { ext: "ods", labelKey: "ods", isRecommended: true },
    { ext: "xlsx", labelKey: "xlsx" },
    { ext: "xls", labelKey: "xls" },
    { ext: "csv", labelKey: "csv" },
    { ext: "tsv", labelKey: "tsv" },
  ],
  slide: [
    { ext: "odp", labelKey: "odp", isRecommended: true },
    { ext: "pptx", labelKey: "pptx" },
    { ext: "ppt", labelKey: "ppt" },
  ],
};

export const getCreateFileInitialState = (
  quickPreset?: { kind: CreateFileKind; extension: string },
) => ({
  kind: quickPreset?.kind ?? "text",
  extension:
    quickPreset?.extension ?? DEFAULT_CREATE_FILE_EXTENSION_BY_KIND.text,
  filenameStem: "",
  extensionSearch: "",
});

export const filterCreateFileExtensionOptions = ({
  options,
  extensionSearch,
  getLabel,
}: {
  options: CreateFileExtensionOption[];
  extensionSearch: string;
  getLabel: (option: CreateFileExtensionOption) => string;
}) => {
  const query = extensionSearch.trim().toLowerCase();
  if (!query) {
    return options;
  }

  return options.filter((option) => {
    const label = getLabel(option).toLowerCase();
    return (
      option.ext.includes(query) ||
      label.includes(query) ||
      `.${option.ext}`.includes(query)
    );
  });
};

export const splitCreateFileExtensionOptions = (
  options: CreateFileExtensionOption[],
) => ({
  recommended: options.filter((option) => option.isRecommended),
  others: options.filter((option) => !option.isRecommended),
});

export const canSubmitCreateFile = ({
  filenameStem,
  isPending,
}: {
  filenameStem: string;
  isPending: boolean;
}) => filenameStem.trim().length > 0 && !isPending;

export const buildCreateFileMutationPayload = ({
  parentId,
  canCreateChildren,
  filenameStem,
  extension,
  kind,
}: {
  parentId?: string;
  canCreateChildren: boolean;
  filenameStem: string;
  extension: string;
  kind: CreateFileKind;
}) => ({
  parentId: canCreateChildren ? parentId : undefined,
  filenameStem,
  extension,
  kind,
});

export const shouldRedirectToMyFiles = (parentId?: string) => !parentId;

export const getRenameInputTitle = (
  item: Pick<Item, "title" | "type">,
) => {
  return item.type === ItemType.FILE
    ? removeFileExtension(item.title)
    : item.title;
};

export const getRenameMutationTitle = ({
  item,
  title,
}: {
  item: Pick<Item, "title" | "type">;
  title: string;
}) => {
  return item.type === ItemType.FILE
    ? preserveKnownExtensionOnRename(item.title, title)
    : title;
};

export const buildNextRenamedRightPanelItem = ({
  currentItem,
  fallbackItem,
  updatedItem,
  title,
}: {
  currentItem?: Item;
  fallbackItem: Item;
  updatedItem: Partial<Item>;
  title: string;
}) => {
  const baseItem = currentItem ?? fallbackItem;

  return {
    ...baseItem,
    ...updatedItem,
    title,
  };
};
