import { Filter } from "@gouvfr-lasuite/ui-kit";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Key } from "react-aria-components";
import { buildExplorerScopeFilterOptions } from "../app-view/explorerTopBarHelpers";

export const ExplorerFilterScope = (props: {
  value: string | null;
  onChange: (value: Key | null) => void;
}) => {
  const { t } = useTranslation();
  const options = useMemo(() => buildExplorerScopeFilterOptions(t), [t]);

  return (
    <Filter
      label={t("explorer.filters.scopes.label")}
      options={options}
      selectedKey={props.value ?? null}
      onSelectionChange={props.onChange}
    />
  );
};
