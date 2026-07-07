import { ItemFilters } from "@/features/drivers/Driver";

export type DatePreset = "today" | "last_7_days" | "last_30_days" | "this_year";

export type DateRange = Pick<
  ItemFilters,
  "updated_at_after" | "updated_at_before"
>;

const pad = (value: number) => String(value).padStart(2, "0");

export const toISODate = (date: Date): string =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

const addDays = (date: Date, days: number): Date => {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
};

export const presetRange = (
  preset: DatePreset,
  today: Date = new Date(),
): DateRange => {
  let after: Date;
  switch (preset) {
    case "today":
      after = today;
      break;
    case "last_7_days":
      after = addDays(today, -6);
      break;
    case "last_30_days":
      after = addDays(today, -29);
      break;
    case "this_year":
      after = new Date(today.getFullYear(), 0, 1);
      break;
  }

  return {
    updated_at_after: toISODate(after),
    updated_at_before: toISODate(today),
  };
};

export const applyDateRange = (
  filters: ItemFilters,
  range: DateRange | null,
): ItemFilters => {
  const next = { ...filters };
  delete next.updated_at_after;
  delete next.updated_at_before;
  return { ...next, ...(range ?? {}) };
};

export const dateRangeFromFilters = (filters: ItemFilters): DateRange | null => {
  if (!filters.updated_at_after && !filters.updated_at_before) {
    return null;
  }

  return {
    updated_at_after: filters.updated_at_after,
    updated_at_before: filters.updated_at_before,
  };
};
