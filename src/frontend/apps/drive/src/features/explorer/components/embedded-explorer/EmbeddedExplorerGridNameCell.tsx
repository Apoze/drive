import React from "react";
import { CellContext } from "@tanstack/react-table";
import { Item, ItemUploadState, LinkReach } from "@/features/drivers/types";
import { useEffect, useMemo, useRef, useState } from "react";
import { Draggable } from "@/features/explorer/components/Draggable";
import { Tooltip } from "@gouvfr-lasuite/cunningham-react";
import { ItemIcon } from "@/features/explorer/components/icons/ItemIcon";
import { useDisableDragGridItem } from "@/features/explorer/components/embedded-explorer/hooks";
import { Icon, IconSize, Spinner } from "@gouvfr-lasuite/ui-kit";
import { useEmbeddedExplorerGirdContext } from "./EmbeddedExplorerGrid";
import { useTranslation } from "react-i18next";
export type EmbeddedExplorerGridNameCellProps = CellContext<Item, string> & {
  children?: React.ReactNode;
};

export const EmbeddedExplorerGridNameCell = (
  params: EmbeddedExplorerGridNameCellProps,
) => {
  const item = params.row.original;
  const { t } = useTranslation();
  const ref = useRef<HTMLSpanElement>(null);
  const [isOverflown, setIsOverflown] = useState(false);
  const { selectedItemsMap, disableItemDragAndDrop } =
    useEmbeddedExplorerGirdContext();
  const isSelected = !!selectedItemsMap[item.id];

  const disableDrag = useDisableDragGridItem(item);
  const isDuplicating = item.upload_state === ItemUploadState.DUPLICATING;

  const renderTitle = () => {
    // We need to have the element holding the ref nested because the Tooltip component
    // seems to make the top-most children ref null.
    return (
      <Draggable
        id={params.cell.id + "-title"}
        item={item}
        style={{ display: "flex", overflow: "hidden" }}
        disabled={disableItemDragAndDrop || isSelected || isDuplicating} // If it's selected then we can drag on the entire cell
      >
        <div className="explorer__grid__item__name__title-wrapper">
          <span className="explorer__grid__item__name__text" ref={ref}>
            {item.title}
            {params.children}
          </span>
          {isDuplicating && (
            <span className="explorer__grid__item__name__duplicating-label">
              {t("explorer.item.duplicating")}
            </span>
          )}
        </div>
      </Draggable>
    );
  };

  useEffect(() => {
    const checkOverflow = () => {
      const element = ref.current;
      // Should always be defined, but just in case.
      if (element) {
        setIsOverflown(element.scrollWidth > element.clientWidth);
      }
    };
    checkOverflow();

    window.addEventListener("resize", checkOverflow);
    return () => {
      window.removeEventListener("resize", checkOverflow);
    };
  }, [item.title]);

  const rightIcon = useMemo(() => {
    let icon: string | null = null;

    if (item.computed_link_reach === LinkReach.PUBLIC) {
      icon = "public";
    } else if (item.nb_accesses && item.nb_accesses > 1) {
      icon = "people";
    }
    return icon;
  }, [item.computed_link_reach, item.link_reach, item.nb_accesses]);

  return (
    <Draggable
      id={params.cell.id}
      item={item}
      disabled={disableDrag || isDuplicating}
    >
      <div className="explorer__grid__item__name">
        {isDuplicating ? (
          <span className="explorer__grid__item__name__spinner">
            <Spinner size="sm" />
          </span>
        ) : (
          <ItemIcon key={item.id} item={item} size={IconSize.LARGE} />
        )}
        {isOverflown ? (
          <Tooltip content={item.title}>{renderTitle()}</Tooltip>
        ) : (
          renderTitle()
        )}
        {rightIcon && (
          <Icon
            name={rightIcon}
            size={IconSize.SMALL}
            color="var(--c--contextuals--content--semantic--neutral--tertiary)"
          />
        )}
      </div>
    </Draggable>
  );
};
