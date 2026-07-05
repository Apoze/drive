import React from "react";
import { Filter } from "@gouvfr-lasuite/ui-kit";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Key } from "react-aria-components";
import { useAppExplorer } from "./AppExplorer";
import { ItemType } from "@/features/drivers/types";
import { useItems } from "../../hooks/useQueries";
import { ItemIcon } from "../icons/ItemIcon";
import {
  buildExplorerScopeFilterOptions,
  buildExplorerTypeFilterOptions,
  buildExplorerWorkspaceFilterOptions,
  getWorkspaceIconSize,
  handleFilterChange,
} from "./explorerTopBarHelpers";

export const ExplorerFilters = () => {
  const { filters, onFiltersChange } = useAppExplorer();

  const onChange = (name: string, value: Key | null) => {
    onFiltersChange?.(
      handleFilterChange(
        filters,
        name,
        value == null ? null : String(value),
      ),
    );
  };

  return (
    <div className="explorer__filters">
      <ExplorerFilterType
        value={filters?.type ?? null}
        onChange={(value) => onChange("type", value)}
      />
    </div>
  );
};

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
      selectedKey={props.value ?? null} // undefined would trigger "uncontrolled components become controlled" warning.
      onSelectionChange={props.onChange}
    />
  );
};

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
      selectedKey={props.value ?? null} // undefined would trigger "uncontrolled components become controlled" warning.
      onSelectionChange={props.onChange}
      isDisabled={props.isDisabled}
    />
  );
};

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
      selectedKey={props.value ?? null} // undefined would trigger "uncontrolled components become controlled" warning.
      onSelectionChange={props.onChange}
    />
  );
};
