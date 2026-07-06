import React, { memo } from "react";
import { flexRender, Row } from "@tanstack/react-table";
import clsx from "clsx";
import { Item, ItemUploadState } from "@/features/drivers/types";
import { Droppable } from "@/features/explorer/components/Droppable";
import { useIsItemSelected } from "@/features/explorer/stores/selectionStore";
import { isEmbeddedExplorerGridDropDisabled } from "./embeddedExplorerGridHelpers";

type EmbeddedExplorerGridRowProps = {
  row: Row<Item>;
  isOvered: boolean;
  onClickRow: (event: React.MouseEvent<HTMLTableRowElement>, row: Row<Item>) => void;
  onContextMenuRow: (
    event: React.MouseEvent<HTMLTableRowElement>,
    row: Row<Item>,
  ) => void;
  onOver: (rowItem: Item, isOver: boolean, draggedItem: Item) => void;
};

const EmbeddedExplorerGridRowComponent = ({
  row,
  isOvered,
  onClickRow,
  onContextMenuRow,
  onOver,
}: EmbeddedExplorerGridRowProps) => {
  const item = row.original;
  const isSelected = useIsItemSelected(item.id);
  const isDuplicating = item.upload_state === ItemUploadState.DUPLICATING;

  return (
    <tr
      className={clsx({
        selectable: !isDuplicating,
        selected: isSelected,
        over: isOvered,
        duplicating: isDuplicating,
      })}
      data-id={item.id}
      tabIndex={0}
      onClick={(event) => onClickRow(event, row)}
      onContextMenu={(event) => onContextMenuRow(event, row)}
    >
      {row.getVisibleCells().map((cell) => {
        const isTitleCell = cell.column.id === "title";
        return (
          <td
            key={cell.id}
            className={clsx("", {
              "c__datagrid__row__cell--actions": cell.column.id === "actions",
              "c__datagrid__row__cell--title": isTitleCell,
            })}
          >
            <Droppable
              id={cell.id}
              item={item}
              disabled={
                isDuplicating ||
                isEmbeddedExplorerGridDropDisabled({ item, isSelected })
              }
              onOver={(isOver, draggedItem) => onOver(item, isOver, draggedItem)}
            >
              {flexRender(cell.column.columnDef.cell, cell.getContext())}
            </Droppable>
          </td>
        );
      })}
    </tr>
  );
};

export const EmbeddedExplorerGridRow = memo(EmbeddedExplorerGridRowComponent);
