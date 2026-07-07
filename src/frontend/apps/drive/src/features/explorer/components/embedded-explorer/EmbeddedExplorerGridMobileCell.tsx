import React from "react";
import { memo } from "react";
import { CellContext } from "@tanstack/react-table";
import { Item } from "@/features/drivers/types";
import { ItemIcon } from "@/features/explorer/components/icons/ItemIcon";
import { timeAgo } from "@/features/explorer/utils/utils";
import { Spinner } from "@gouvfr-lasuite/ui-kit";
import { useTransientItem } from "../../hooks/useTransientItem";
type EmbeddedExplorerGridMobileCellProps = CellContext<Item, unknown>;

const EmbeddedExplorerGridMobileCellComponent = (
  params: EmbeddedExplorerGridMobileCellProps,
) => {
  const item = params.row.original;
  const transientItem = useTransientItem(item);

  return (
    <div className="explorer__grid__item__mobile">
      {transientItem.isTransient ? (
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
            {transientItem.label
              ? transientItem.label
              : timeAgo(new Date(item.updated_at))}
          </span>
        </div>
      </div>
    </div>
  );
};

export const EmbeddedExplorerGridMobileCell = memo(
  EmbeddedExplorerGridMobileCellComponent,
);
