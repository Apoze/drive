import { getDriver } from "@/features/config/Config";
import { ItemFilters } from "@/features/drivers/Driver";
import { Item } from "@/features/drivers/types";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Key } from "react-aria-components";
import { useModals } from "@gouvfr-lasuite/cunningham-react";
import {
  NavigationEventType,
  useGlobalExplorer,
} from "../../GlobalExplorerContext";
import { handleFilterChange } from "@/features/explorer/components/filters";
import { clearFromRoute } from "@/features/explorer/utils/utils";
import { messageModalTrashNavigate } from "../../trash/utils";
import { useIsMinimalLayout } from "@/utils/useLayout";
import {
  activateExplorerSearchItem,
  buildExplorerSearchQuery,
  shouldClearExplorerSearchResults,
} from "./searchModalHelpers";
import {
  applyDateRange,
  DateRange,
} from "@/features/explorer/utils/dateFilters";

export const useExplorerSearchController = ({
  isOpen,
  onClose,
  defaultFilters,
}: {
  isOpen: boolean;
  onClose: () => void;
  defaultFilters?: ItemFilters;
}) => {
  const [inputValue, setInputValue] = useState("");
  const [filters, setFilters] = useState<ItemFilters>(defaultFilters || {});
  const searchUserTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const inputTextSelected = useRef(false);

  const driver = useMemo(() => getDriver(), []);
  const modals = useModals();
  const isMinimalLayout = useIsMinimalLayout();
  const { onNavigate, openSinglePreview } = useGlobalExplorer();

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    if (searchUserTimeoutRef.current) {
      clearTimeout(searchUserTimeoutRef.current);
    }

    if (shouldClearExplorerSearchResults(inputValue, filters)) {
      setLoading(false);
      setItems((currentItems) => (currentItems.length > 0 ? [] : currentItems));
      return;
    }

    searchUserTimeoutRef.current = setTimeout(async () => {
      setLoading(true);
      const nextItems = await driver.searchItems(
        buildExplorerSearchQuery(filters, inputValue),
      );
      setItems(nextItems);
      setLoading(false);
    }, 300);

    return () => {
      if (searchUserTimeoutRef.current) {
        clearTimeout(searchUserTimeoutRef.current);
      }
    };
  }, [driver, filters, inputValue, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      inputTextSelected.current = false;
    }
  }, [isOpen]);

  const onFilterChange = (name: string, value: Key | null) => {
    setFilters((currentFilters) =>
      handleFilterChange(currentFilters, name, value),
    );
  };

  const onModifiedChange = (range: DateRange | null) => {
    setFilters((currentFilters) => applyDateRange(currentFilters, range));
  };

  const bindContainerRef = (ref: HTMLDivElement | null) => {
    if (inputTextSelected.current) {
      return;
    }

    const input = ref?.querySelector(
      ".quick-search-input-container input",
    ) as HTMLInputElement | null;
    input?.focus();
    input?.select();
    inputTextSelected.current = true;
  };

  const onItemClick = (item: Item) => {
    activateExplorerSearchItem({
      item,
      onNavigate: (event) => {
        clearFromRoute();
        onNavigate({
          item: event.item,
          type: NavigationEventType.ITEM,
        });
      },
      openSinglePreview,
      onClose,
      onTrashFolderBlocked: () => messageModalTrashNavigate(modals),
      onFileActivated: () => {
        inputTextSelected.current = false;
      },
    });
  };

  return {
    inputValue,
    loading,
    items,
    filters,
    isMinimalLayout,
    showResetFilters: Object.keys(filters).length > 0,
    onInputChange: setInputValue,
    onFilterChange,
    onModifiedChange,
    onResetFilters: () => setFilters({}),
    onItemClick,
    bindContainerRef,
  };
};
