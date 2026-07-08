import {
  FileIcon,
  Filter,
  FilterOption,
  IconSize,
} from "@gouvfr-lasuite/ui-kit";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Key } from "react-aria-components";

const CATEGORY_OPTIONS: { value: string; mimetype: string }[] = [
  { value: "doc", mimetype: "application/vnd.oasis.opendocument.text" },
  {
    value: "powerpoint",
    mimetype: "application/vnd.oasis.opendocument.presentation",
  },
  { value: "calc", mimetype: "application/vnd.oasis.opendocument.spreadsheet" },
  { value: "pdf", mimetype: "application/pdf" },
  { value: "image", mimetype: "image/png" },
  { value: "video", mimetype: "video/mp4" },
  { value: "audio", mimetype: "audio/mpeg" },
  { value: "archive", mimetype: "application/zip" },
  { value: "other", mimetype: "text/plain" },
];

export const ExplorerFilterCategory = (props: {
  value: string | null;
  onChange: (value: Key | null) => void;
}) => {
  const { t } = useTranslation();

  const options: FilterOption[] = useMemo(
    () =>
      CATEGORY_OPTIONS.map(({ value, mimetype }) => ({
        label: t(`explorer.filters.category.options.${value}`),
        value,
        render: () => (
          <div className="explorer__filters__item">
            <FileIcon
              file={{ mimetype, title: "" }}
              size={IconSize.SMALL}
              type="mini"
            />
            {t(`explorer.filters.category.options.${value}`)}
          </div>
        ),
      })),
    [t],
  );

  return (
    <Filter
      label={t("explorer.filters.category.label")}
      options={options}
      selectedKey={props.value ?? null}
      onSelectionChange={props.onChange}
    />
  );
};
