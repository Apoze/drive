import React from "react";
import { CellContext } from "@tanstack/react-table";
import { Item, ItemUploadState } from "@/features/drivers/types";
import { ItemIcon } from "@/features/explorer/components/icons/ItemIcon";
import { timeAgo } from "@/features/explorer/utils/utils";
import { Spinner } from "@gouvfr-lasuite/ui-kit";
import { useTranslation } from "react-i18next";
type EmbeddedExplorerGridMobileCellProps = CellContext<Item, unknown>;

export const EmbeddedExplorerGridMobileCell = (
  params: EmbeddedExplorerGridMobileCellProps,
) => {
  const item = params.row.original;
  const { t } = useTranslation();
  const isDuplicating = item.upload_state === ItemUploadState.DUPLICATING;

  return (
    <div className="explorer__grid__item__mobile">
      {isDuplicating ? (
        <span className="explorer__grid__item__mobile__spinner">
          <Spinner size="sm" />
        </span>
      ) : (
        <ItemIcon key={item.id} item={item} />
      )}
      <div className="explorer__grid__item__mobile__info">
        <div className="explorer__grid__item__mobile__info__title">
          <span className="explorer__grid__item__name__text">{item.title}</span>
        </div>
        <div className="explorer__grid__item__mobile__info__meta">
          <span>
            {isDuplicating
              ? t("explorer.item.duplicating")
              : timeAgo(new Date(item.updated_at))}
          </span>
        </div>
      </div>
    </div>
  );
};
