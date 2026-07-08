import { ItemFilters } from "@/features/drivers/Driver";
import {
  applyDateRange,
  presetRange,
} from "@/features/explorer/utils/dateFilters";

export const ALL = "all";

export const handleFilterChange = (
  filters: ItemFilters = {},
  name: string,
  value: unknown,
) => {
  if (value === ALL || !value) {
    const newFilters = { ...filters };
    delete newFilters[name as keyof ItemFilters];
    return newFilters;
  }

  return { ...filters, [name]: value };
};

export const convertFiltersToQueryParams = (
  filters: ItemFilters,
): Omit<ItemFilters, "modified"> => {
  let newFilters = { ...filters };

  delete newFilters.modified;
  const actualDateRange =
    filters.modified?.customRange ?? presetRange(filters.modified?.key);
  newFilters = applyDateRange(newFilters, actualDateRange);

  return newFilters;
};
