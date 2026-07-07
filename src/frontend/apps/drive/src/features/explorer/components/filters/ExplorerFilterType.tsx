import { Filter } from "@gouvfr-lasuite/ui-kit";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Key } from "react-aria-components";
import { ItemType } from "@/features/drivers/types";
import { buildExplorerTypeFilterOptions } from "../app-view/explorerTopBarHelpers";

export const ExplorerFilterType = (props: {
  value: ItemType | null;
  onChange: (value: Key | null) => void;
}) => {
  const { t } = useTranslation();
  const typeOptions = useMemo(() => buildExplorerTypeFilterOptions(t), [t]);

  return (
    <Filter
      label={t("explorer.filters.type.label")}
      options={typeOptions}
      selectedKey={props.value ?? null}
      onSelectionChange={props.onChange}
    />
  );
};
