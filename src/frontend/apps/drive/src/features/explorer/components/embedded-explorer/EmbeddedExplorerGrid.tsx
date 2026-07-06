import React from "react";
import { Item, ItemType } from "@/features/drivers/types";
import {
  createContext,
  Dispatch,
  SetStateAction,
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
  flexRender,
} from "@tanstack/react-table";
import { useReactTable } from "@tanstack/react-table";
import { getCoreRowModel } from "@tanstack/react-table";
import {
  NavigationEventType,
} from "@/features/explorer/components/GlobalExplorerContext";
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
import { useTableKeyboardNavigation } from "@/features/explorer/hooks/useTableKeyboardNavigation";
import clsx from "clsx";
import { isTablet } from "@/features/ui/components/responsive/ResponsiveDivs";
import { Droppable } from "@/features/explorer/components/Droppable";
import { useOptionalDragItemContext } from "@/features/explorer/components/ExplorerDndProvider";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { MenuItem, useContextMenuContext } from "@gouvfr-lasuite/ui-kit";
import { useItemActionMenuItems } from "../../hooks/useItemActionMenuItems";
import { MoveItemsModalLauncher } from "../moveItemsModalLauncher";
import { isEmbeddedExplorerGridDropDisabled } from "./embeddedExplorerGridHelpers";
import {
  ColumnConfig,
  ColumnPreferences,
  ColumnType,
  DEFAULT_COLUMN_PREFERENCES,
  SortState,
} from "../../types/columns";
import { SortableColumnHeader } from "./headers/SortableColumnHeader";
import { CustomizableColumnHeader } from "./headers/CustomizableColumnHeader";

export type EmbeddedExplorerGridProps = {
  isCompact?: boolean;
  enableMetaKeySelection?: boolean;
  disableItemDragAndDrop?: boolean;
  clearRightPanelItem?: () => void;
  items: AppExplorerProps["childrenItems"];
  gridActionsCell?: AppExplorerProps["gridActionsCell"];
  gridNameCell?: (params: EmbeddedExplorerGridNameCellProps) => React.ReactNode;
  onNavigate: (event: NavigationEvent) => void;
  selectedItems?: Item[];
  setSelectedItems?: Dispatch<SetStateAction<Item[]>>;
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

type EmbeddedExplorerGridContextType = EmbeddedExplorerGridProps & {
  selectedItemsMap: Record<string, Item>;
  openMoveModal: () => void;
  closeMoveModal: () => void;
  setMoveItem: (item: Item) => void;
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

  const selectedItems = props.selectedItems ?? [];
  const selectedItemsMap = useMemo(() => {
    const map: Record<string, Item> = {};
    selectedItems.forEach((item) => {
      map[item.id] = item;
    });
    return map;
  }, [selectedItems]);

  const dndContext = useOptionalDragItemContext();
  const [localOveredItemIds, setLocalOveredItemIds] = useState<
    Record<string, boolean>
  >({});
  const overedItemIds = dndContext?.overedItemIds ?? localOveredItemIds;
  const setOveredItemIds =
    dndContext?.setOveredItemIds ?? setLocalOveredItemIds;

  const lastSelectedRowRef = useRef<string | null>(null);

  const col1CellComponent = props.column1Config?.cell;
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

    [col1CellComponent, col2CellComponent, props.isCompact],
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

  const contextValue = useMemo<EmbeddedExplorerGridContextType>(
    () => ({
      ...props,
      selectedItemsMap,
      openMoveModal: moveModal.open,
      closeMoveModal: moveModal.close,
      setMoveItem,
      isActionModalOpen,
      setIsActionModalOpen,
    }),
    [
      props,
      selectedItemsMap,
      moveModal.open,
      moveModal.close,
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
              {table.getRowModel().rows.map((row) => {
                const isSelected = !!selectedItemsMap[row.original.id];
                const isOvered = !!overedItemIds[row.original.id];
                return (
                  <tr
                    key={row.original.id}
                    className={clsx("selectable", {
                      selected: isSelected,
                      over: isOvered,
                    })}
                    data-id={row.original.id}
                    tabIndex={0}
                    onClick={(e) => {
                      const target = e.target as HTMLElement;
                      const closest = target.closest("tr");
                      // Because if we use modals or other components, even with a Portal, React triggers events on the original parent.
                      // So we check that the clicked element is indeed an element of the table.
                      if (!closest) {
                        return;
                      }

                      // In SDK mode we want the popup to behave like desktop. For instance we want the simple click to
                      // trigger selection, not to open a file as it is the case on mobile.
                      const isMobile =
                        isTablet() && props.displayMode !== "sdk";

                      // Single click to select/deselect the item
                      if (!isMobile && e.detail === 1) {
                        if (!canSelect(row.original)) {
                          return;
                        }

                        if (
                          props.enableMetaKeySelection &&
                          e.shiftKey &&
                          lastSelectedRowRef.current
                        ) {
                          // Get all rows between last selected and current
                          const rows = table.getRowModel().rows;
                          const lastSelectedIndex = rows.findIndex(
                            (r) => r.id === lastSelectedRowRef.current,
                          );
                          const currentIndex = rows.findIndex(
                            (r) => r.id === row.id,
                          );

                          if (lastSelectedIndex !== -1 && currentIndex !== -1) {
                            const startIndex = Math.min(
                              lastSelectedIndex,
                              currentIndex,
                            );
                            const endIndex = Math.max(
                              lastSelectedIndex,
                              currentIndex,
                            );

                            const newSelection = [...selectedItems];
                            for (let i = startIndex; i <= endIndex; i++) {
                              if (!selectedItemsMap[rows[i].original.id]) {
                                newSelection.push(rows[i].original);
                              }
                            }

                            props.setSelectedItems?.(newSelection);
                          }
                        } else if (
                          props.enableMetaKeySelection &&
                          (e.metaKey ||
                            e.ctrlKey ||
                            props.displayMode === "sdk")
                        ) {
                          // Toggle the selected item.
                          props.setSelectedItems?.((value) => {
                            let newValue = [...value];
                            if (
                              newValue.find(
                                (item) => item.id == row.original.id,
                              )
                            ) {
                              newValue = newValue.filter(
                                (item) => item.id !== row.original.id,
                              );
                            } else {
                              newValue.push(row.original);
                            }
                            return newValue;
                          });
                          if (!isSelected) {
                            lastSelectedRowRef.current = row.id;
                          }
                        } else {
                          props.setSelectedItems?.([row.original]);
                          lastSelectedRowRef.current = row.id;
                          props.clearRightPanelItem?.();
                        }
                      }

                      // Double click to open the item
                      if (isMobile || e.detail === 2) {
                        if (row.original.type === ItemType.FOLDER) {
                          props.onNavigate({
                            type: NavigationEventType.ITEM,
                            item: row.original,
                          });
                        } else {
                          props.onFileClick?.(row.original);
                        }
                      }
                    }}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      const items =
                        props.getContextMenuItems?.(row.original) ??
                        getItemActionMenuItems(row.original);
                      contextMenu.open({
                        position: { x: e.clientX, y: e.clientY },
                        items,
                      });
                    }}
                  >
                    {row.getVisibleCells().map((cell, index) => {
                      const isTitleCell = cell.column.id === "title";
                      return (
                        <td
                          key={cell.id}
                          className={clsx("", {
                            "c__datagrid__row__cell--actions":
                              cell.column.id === "actions",
                            "c__datagrid__row__cell--title": isTitleCell,
                          })}
                        >
                          <Droppable
                            id={cell.id}
                            item={row.original}
                            disabled={
                              isEmbeddedExplorerGridDropDisabled({
                                item: row.original,
                                isSelected,
                              })
                            }
                            onOver={(isOver, item) => {
                              setOveredItemIds?.((prev) => ({
                                ...prev,
                                [row.original.id]:
                                  item.id === row.original.id ? false : isOver,
                              }));
                            }}
                          >
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext(),
                            )}
                          </Droppable>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
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
