import { Key } from "react-aria-components";
import { useAuth } from "@/features/auth/Auth";
import { ItemFilters } from "@/features/drivers/Driver";
import { useAppExplorer } from "@/features/explorer/components/app-view/AppExplorer";
import {
  applyDateRange,
  DateRange,
  dateRangeFromFilters,
} from "@/features/explorer/utils/dateFilters";
import { ALL, handleFilterChange } from "./filterUtils";
import { ExplorerFilterCategory } from "./ExplorerFilterCategory";
import { ExplorerFilterContact } from "./ExplorerFilterContact";
import { ExplorerFilterModified } from "./ExplorerFilterModified";

export const ExplorerFilters = () => {
  const { filters, onFiltersChange } = useAppExplorer();
  const { user } = useAuth();

  const onChange = (name: string, value: Key | null) => {
    onFiltersChange?.(handleFilterChange(filters, name, value));
  };

  const onModifiedChange = (range: DateRange | null) => {
    onFiltersChange?.(applyDateRange(filters ?? {}, range));
  };

  return (
    <div className="explorer__filters">
      <ExplorerFilterCategory
        value={filters?.category ?? null}
        onChange={(value) => onChange("category", value)}
      />
      {user && (
        <ExplorerFilterContact
          value={filters?.contact ?? null}
          onChange={(value) => onChange("contact", value ?? ALL)}
        />
      )}
      <ExplorerFilterModified
        value={dateRangeFromFilters((filters ?? {}) as ItemFilters)}
        onChange={onModifiedChange}
      />
    </div>
  );
};
