import { Filter } from "@gouvfr-lasuite/ui-kit";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Key } from "react-aria-components";
import { useItems } from "../../hooks/useQueries";
import { ItemIcon } from "../icons/ItemIcon";
import {
  buildExplorerWorkspaceFilterOptions,
  getWorkspaceIconSize,
} from "../app-view/explorerTopBarHelpers";

export const ExplorerFilterWorkspace = (props: {
  value: string | null;
  onChange: (value: Key | null) => void;
  isDisabled?: boolean;
}) => {
  const { t } = useTranslation();
  const { data: items } = useItems();

  const options = useMemo(
    () =>
      buildExplorerWorkspaceFilterOptions({
        items,
        t,
        renderIcon: (item) => (
          <ItemIcon item={item} size={getWorkspaceIconSize()} />
        ),
      }),
    [items, t],
  );

  if (!options) {
    return null;
  }

  return (
    <Filter
      label={t("explorer.filters.folders.label")}
      options={options}
      selectedKey={props.value ?? null}
      onSelectionChange={props.onChange}
      isDisabled={props.isDisabled}
    />
  );
};
