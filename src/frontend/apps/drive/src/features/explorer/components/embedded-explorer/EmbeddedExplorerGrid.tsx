import React from "react";
import { Item, ItemType, ItemUploadState } from "@/features/drivers/types";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import { useTranslation } from "react-i18next";
import {
  CellContext,
  createColumnHelper,
  Row,
} from "@tanstack/react-table";
import { useReactTable } from "@tanstack/react-table";
import { getCoreRowModel } from "@tanstack/react-table";
import { NavigationEventType } from "@/features/explorer/components/GlobalExplorerContext";
import type { AppExplorerProps } from "@/features/explorer/components/app-view/AppExplorer";
import type {
  GlobalExplorerContextType,
  NavigationEvent,
} from "@/features/explorer/components/GlobalExplorerContext";
import { EmbeddedExplorerGridMobileCell } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridMobileCell";
import {
  EmbeddedExplorerGridNameCell,
  EmbeddedExplorerGridNameCellProps,
} from "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridNameCell";
import { EmbeddedExplorerGridActionsCell } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridActionsCell";
import { EmbeddedExplorerGridUpdatedAtCell } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridUpdatedAtCell";
import { useTableKeyboardNavigation } from "@/features/explorer/hooks/useTableKeyboardNavigation";
import clsx from "clsx";
import { isTablet } from "@/features/ui/components/responsive/ResponsiveDivs";
import { useOptionalDragItemContext } from "@/features/explorer/components/ExplorerDndProvider";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { MenuItem, useContextMenuContext } from "@gouvfr-lasuite/ui-kit";
import { useItemActionMenuItems } from "../../hooks/useItemActionMenuItems";
import { MoveItemsModalLauncher } from "../moveItemsModalLauncher";
import {
  ColumnConfig,
  ColumnPreferences,
  ColumnType,
  DEFAULT_COLUMN_PREFERENCES,
  SortState,
} from "../../types/columns";
import { SortableColumnHeader } from "./headers/SortableColumnHeader";
import { CustomizableColumnHeader } from "./headers/CustomizableColumnHeader";
import { useDuplicatingItemsPoller } from "../../hooks/useDuplicatingItemsPoller";
import { useSelectionStore } from "@/features/explorer/stores/selectionStore";
import { EmbeddedExplorerGridRow } from "./EmbeddedExplorerGridRow";

export type EmbeddedExplorerGridProps = {
  isCompact?: boolean;
  enableMetaKeySelection?: boolean;
  disableItemDragAndDrop?: boolean;
  clearRightPanelItem?: () => void;
  items: AppExplorerProps["childrenItems"];
  gridActionsCell?: AppExplorerProps["gridActionsCell"];
  gridNameCell?: (params: EmbeddedExplorerGridNameCellProps) => React.ReactNode;
  onNavigate: (event: NavigationEvent) => void;
  parentItem?: Item;
  displayMode?: GlobalExplorerContextType["displayMode"];
  canSelect?: (item: Item) => boolean;
  onFileClick?: (item: Item) => void;
  disableKeyboardNavigation?: boolean;
  getContextMenuItems?: (item: Item) => MenuItem[];
  // Custom columns
  sortState?: SortState;
  onSort?: (columnId: "title" | ColumnType) => void;
  prefs?: ColumnPreferences;
  onChangeColumn?: (slot: "column1" | "column2", type: ColumnType) => void;
  column1Config?: ColumnConfig;
  column2Config?: ColumnConfig;
};

const EMPTY_ARRAY: Item[] = [];
const columnHelper = createColumnHelper<Item>();
const renderDefaultInfoCell = (context: CellContext<Item, unknown>) => (
  <EmbeddedExplorerGridUpdatedAtCell
    {...(context as CellContext<Item, Date>)}
  />
);

type EmbeddedExplorerGridContextType = {
  disableItemDragAndDrop?: boolean;
  getContextMenuItems?: (item: Item) => MenuItem[];
  isActionModalOpen: boolean;
  setIsActionModalOpen: (value: boolean) => void;
};

export const EmbeddedExplorerGridContext = createContext<
  EmbeddedExplorerGridContextType | undefined
>(undefined);

export const useEmbeddedExplorerGirdContext = () => {
  const context = useContext(EmbeddedExplorerGridContext);
  if (!context) {
    throw new Error(
      "useEmbeddedExplorerGirdContext must be used within an EmbeddedExplorerGridContext",
    );
  }
  return context;
};

/**
 * Standalone component to display a list of items in a table.
 *
 * It provides:
 * - Compact and Full mode
 * - Keyboard navigation
 * - Selection
 * - Over
 * - Actions
 * - Mobile support
 * - Table support
 * - Droppable support
 * - Right panel support
 */
export const EmbeddedExplorerGrid = (props: EmbeddedExplorerGridProps) => {
  const { t } = useTranslation();

  const [moveItem, setMoveItem] = useState<Item | null>(null);
  const moveModal = useModal();
  const [isActionModalOpen, setIsActionModalOpen] = useState(false);
  const { getMenuItems: getItemActionMenuItems, modals: itemActionModals } =
    useItemActionMenuItems({
      onModalOpenChange: setIsActionModalOpen,
  });
  const contextMenu = useContextMenuContext();
  useDuplicatingItemsPoller(props.items ?? EMPTY_ARRAY);
  const selectionStore = useSelectionStore();

  const dndContext = useOptionalDragItemContext();
  const [localOveredItemIds, setLocalOveredItemIds] = useState<
    Record<string, boolean>
  >({});
  const overedItemIds = dndContext?.overedItemIds ?? localOveredItemIds;
  const setOveredItemIds =
    dndContext?.setOveredItemIds ?? setLocalOveredItemIds;

  const lastSelectedRowRef = useRef<string | null>(null);

  const col1CellComponent = props.column1Config?.cell ?? renderDefaultInfoCell;
  const col2CellComponent = props.column2Config?.cell;

  const columns = useMemo(
    () => [
      columnHelper.display({
        id: "mobile",
        cell: EmbeddedExplorerGridMobileCell,
      }),
      columnHelper.accessor("title", {
        id: "title",
        header: t("explorer.grid.name"),
        cell: props.gridNameCell ?? EmbeddedExplorerGridNameCell,
      }),
      ...(props.isCompact
        ? []
        : [
            columnHelper.display({
              id: "info-col-1",
              cell: col1CellComponent ?? EmbeddedExplorerGridMobileCell,
            }),
            columnHelper.display({
              id: "info-col-2",
              cell: col2CellComponent ?? EmbeddedExplorerGridMobileCell,
            }),
            columnHelper.display({
              id: "actions",
              cell: props.gridActionsCell ?? EmbeddedExplorerGridActionsCell,
            }),
          ]),
    ],

    [
      col1CellComponent,
      col2CellComponent,
      props.gridActionsCell,
      props.gridNameCell,
      props.isCompact,
      t,
    ],
  );

  const table = useReactTable({
    data: props.items ?? EMPTY_ARRAY,
    columns,
    getCoreRowModel: getCoreRowModel(),
    enableRowSelection: true,
  });

  const tableRef = useRef<HTMLTableElement>(null);
  const { onKeyDown } = useTableKeyboardNavigation({
    table,
    tableRef,
    isDisabled: isActionModalOpen || props.disableKeyboardNavigation,
  });

  const handleCloseMoveModal = () => {
    moveModal.close();
    setMoveItem(null);
  };

  const canSelect = props.canSelect ?? (() => true);

  const handleSortTitle = useCallback(
    (id: string) => props.onSort?.(id as "title" | ColumnType),
    [props.onSort],
  );

  const handleSortColumn = useCallback(
    (id: string) => props.onSort?.(id as ColumnType),
    [props.onSort],
  );

  const handleChangeCol1 = useCallback(
    (type: ColumnType) => props.onChangeColumn?.("column1", type),
    [props.onChangeColumn],
  );

  const handleChangeCol2 = useCallback(
    (type: ColumnType) => props.onChangeColumn?.("column2", type),
    [props.onChangeColumn],
  );

  const handleRowOver = useCallback(
    (rowItem: Item, isOver: boolean, draggedItem: Item) => {
      setOveredItemIds?.((prev) => ({
        ...prev,
        [rowItem.id]: draggedItem.id === rowItem.id ? false : isOver,
      }));
    },
    [setOveredItemIds],
  );

  const handleRowClick = useCallback(
    (e: React.MouseEvent<HTMLTableRowElement>, row: Row<Item>) => {
      const item = row.original;
      const target = e.target as HTMLElement;
      const closest = target.closest("tr");
      if (!closest) {
        return;
      }
      if (item.upload_state === ItemUploadState.DUPLICATING) {
        return;
      }

      const isMobile = isTablet() && props.displayMode !== "sdk";

      if (!isMobile && e.detail === 1) {
        if (!canSelect(item)) {
          return;
        }

        if (
          props.enableMetaKeySelection &&
          e.shiftKey &&
          lastSelectedRowRef.current
        ) {
          const rows = table.getRowModel().rows;
          const lastSelectedIndex = rows.findIndex(
            (currentRow) => currentRow.id === lastSelectedRowRef.current,
          );
          const currentIndex = rows.findIndex(
            (currentRow) => currentRow.id === row.id,
          );

          if (lastSelectedIndex !== -1 && currentIndex !== -1) {
            const startIndex = Math.min(lastSelectedIndex, currentIndex);
            const endIndex = Math.max(lastSelectedIndex, currentIndex);

            selectionStore.setSelectedItems((previousItems) => {
              const nextById = new Map(
                previousItems.map((selectedItem) => [
                  selectedItem.id,
                  selectedItem,
                ]),
              );
              for (let i = startIndex; i <= endIndex; i++) {
                nextById.set(rows[i].original.id, rows[i].original);
              }
              return [...nextById.values()];
            });
          }
        } else if (
          props.enableMetaKeySelection &&
          (e.metaKey || e.ctrlKey || props.displayMode === "sdk")
        ) {
          selectionStore.setSelectedItems((previousItems) => {
            if (previousItems.some((selectedItem) => selectedItem.id === item.id)) {
              return previousItems.filter(
                (selectedItem) => selectedItem.id !== item.id,
              );
            }
            return [...previousItems, item];
          });
          if (!selectionStore.isSelected(item.id)) {
            lastSelectedRowRef.current = row.id;
          }
        } else {
          selectionStore.setSelectedItems([item]);
          lastSelectedRowRef.current = row.id;
          props.clearRightPanelItem?.();
        }
      }

      if (isMobile || e.detail === 2) {
        if (item.type === ItemType.FOLDER) {
          props.onNavigate({
            type: NavigationEventType.ITEM,
            item,
          });
        } else {
          props.onFileClick?.(item);
        }
      }
    },
    [canSelect, props, selectionStore, table],
  );

  const handleRowContextMenu = useCallback(
    (e: React.MouseEvent<HTMLTableRowElement>, row: Row<Item>) => {
      if (props.displayMode === "sdk") {
        return;
      }

      e.preventDefault();
      e.stopPropagation();

      const item = row.original;
      if (item.upload_state === ItemUploadState.DUPLICATING) {
        return;
      }

      selectionStore.setSelectedItems([item]);
      const items =
        props.getContextMenuItems?.(item) ?? getItemActionMenuItems(item);
      contextMenu.open({
        position: { x: e.clientX, y: e.clientY },
        items,
      });
    },
    [
      contextMenu,
      getItemActionMenuItems,
      props.displayMode,
      props.getContextMenuItems,
      selectionStore,
    ],
  );

  const contextValue = useMemo<EmbeddedExplorerGridContextType>(
    () => ({
      disableItemDragAndDrop: props.disableItemDragAndDrop,
      getContextMenuItems: props.getContextMenuItems,
      isActionModalOpen,
      setIsActionModalOpen,
    }),
    [
      props.disableItemDragAndDrop,
      props.getContextMenuItems,
      isActionModalOpen,
    ],
  );

  return (
    <>
      {/* The context is only here to avoid the rerendering of react table cells
      when passing props to cells, with a context // we avoid that by passing
      props via context, but it's quite overkill, unfortunatly we did not find a
      better solution. */}
      <EmbeddedExplorerGridContext.Provider value={contextValue}>
        <div
          className={clsx("c__datagrid__table__container", {
            explorer__compact: props.isCompact,
          })}
        >
          <table ref={tableRef} tabIndex={0} onKeyDown={onKeyDown}>
            <thead>
              <tr>
                {/* This one stands for the mobile column */}
                <th></th>
                <th className="explorer__grid__th--title">
                  <SortableColumnHeader
                    label={t("explorer.grid.name")}
                    columnId="title"
                    sortState={props.sortState ?? null}
                    onSort={handleSortTitle}
                  />
                </th>
                {!props.isCompact && (
                  <>
                    <th className="explorer__grid__th--info-col-1">
                      {props.prefs && props.column1Config ? (
                        <CustomizableColumnHeader
                          slot="column1"
                          currentType={props.prefs.column1}
                          defaultType={DEFAULT_COLUMN_PREFERENCES.column1}
                          sortState={props.sortState ?? null}
                          onSort={handleSortColumn}
                          onChangeColumn={handleChangeCol1}
                        />
                      ) : (
                        <div className="c__datagrid__header fs-h5 c__datagrid__header--sortable">
                          {t("explorer.grid.last_update")}
                        </div>
                      )}
                    </th>
                    <th className="explorer__grid__th--info-col-2">
                      {props.prefs && props.column2Config ? (
                        <CustomizableColumnHeader
                          slot="column2"
                          currentType={props.prefs.column2}
                          defaultType={DEFAULT_COLUMN_PREFERENCES.column2}
                          sortState={props.sortState ?? null}
                          onSort={handleSortColumn}
                          onChangeColumn={handleChangeCol2}
                        />
                      ) : null}
                    </th>
                  </>
                )}
                {!props.isCompact && (
                  <th className="explorer__grid__th--actions"></th>
                )}
              </tr>
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <EmbeddedExplorerGridRow
                  key={row.original.id}
                  row={row}
                  isOvered={!!overedItemIds[row.original.id]}
                  onClickRow={handleRowClick}
                  onContextMenuRow={handleRowContextMenu}
                  onOver={handleRowOver}
                />
              ))}
            </tbody>
          </table>
        </div>
        <MoveItemsModalLauncher
          isOpen={moveModal.isOpen}
          onClose={handleCloseMoveModal}
          itemsToMove={moveItem ? [moveItem] : []}
          initialFolderId={props.parentItem?.id}
        />
        {itemActionModals}
      </EmbeddedExplorerGridContext.Provider>
    </>
  );
};

export type EmbeddedExplorerGridTypeCellProps = CellContext<Item, string> & {
  children?: React.ReactNode;
};
