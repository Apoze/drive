import { Item } from "@/features/drivers/types";
import { AppExplorer, AppExplorerProps } from "@/features/explorer/components/app-view/AppExplorer";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { flattenBrowsePages } from "./browseTemplateUtils";

type InfiniteBrowseData<TPage> = {
  pages: TPage[];
};

export type BrowseExplorerTemplateProps<TPage, TItem extends Item> = Omit<
  AppExplorerProps,
  "childrenItems"
> & {
  data?: InfiniteBrowseData<TPage>;
  mapPageItems: (page: TPage) => TItem[];
  isError?: boolean;
  errorLabel?: string;
  loadingLabel?: string;
  onRetry?: () => void;
  renderAfterExplorer?: (childrenItems: TItem[]) => React.ReactNode;
};

export const BrowseExplorerTemplate = <TPage, TItem extends Item>({
  data,
  mapPageItems,
  isError = false,
  errorLabel,
  loadingLabel,
  onRetry,
  renderAfterExplorer,
  isLoading,
  ...appExplorerProps
}: BrowseExplorerTemplateProps<TPage, TItem>) => {
  const { t } = useTranslation();
  const childrenItems = useMemo(
    () => flattenBrowsePages(data?.pages, mapPageItems),
    [data?.pages, mapPageItems],
  );

  if (isLoading && !data && loadingLabel) {
    return <div>{loadingLabel}</div>;
  }

  if (isError && errorLabel) {
    return (
      <div>
        <div>{errorLabel}</div>
        {onRetry && (
          <Button variant="tertiary" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        )}
      </div>
    );
  }

  return (
    <>
      <AppExplorer
        {...appExplorerProps}
        childrenItems={childrenItems}
        isLoading={isLoading}
      />
      {renderAfterExplorer?.(childrenItems)}
    </>
  );
};
