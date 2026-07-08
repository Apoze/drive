import {
  applyDateRange,
  dateRangeFromFilters,
  presetRange,
  toISODate,
} from "../dateFilters";

describe("presetRange", () => {
  const today = new Date(2026, 4, 29);

  it("returns the current day for the today preset", () => {
    expect(presetRange("today", today)).toEqual({
      updated_at_after: "2026-05-29",
      updated_at_before: "2026-05-29",
    });
  });

  it("spans the last 7 days, today included", () => {
    expect(presetRange("last_7_days", today)).toEqual({
      updated_at_after: "2026-05-23",
      updated_at_before: "2026-05-29",
    });
  });

  it("spans the last 30 days, today included", () => {
    expect(presetRange("last_30_days", today)).toEqual({
      updated_at_after: "2026-04-30",
      updated_at_before: "2026-05-29",
    });
  });

  it("spans from the first day of the year", () => {
    expect(presetRange("this_year", today)).toEqual({
      updated_at_after: "2026-01-01",
      updated_at_before: "2026-05-29",
    });
  });
});

describe("date filter helpers", () => {
  it("formats a local date as YYYY-MM-DD", () => {
    expect(toISODate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });

  it("applies and extracts date ranges without preserving stale bounds", () => {
    const filters = applyDateRange(
      {
        title: "report",
        updated_at_after: "2026-01-01",
        updated_at_before: "2026-01-02",
      },
      {
        updated_at_after: "2026-05-01",
        updated_at_before: "2026-05-29",
      },
    );

    expect(filters).toEqual({
      title: "report",
      updated_at_after: "2026-05-01",
      updated_at_before: "2026-05-29",
    });
    expect(dateRangeFromFilters(filters)).toEqual({
      updated_at_after: "2026-05-01",
      updated_at_before: "2026-05-29",
    });
    expect(dateRangeFromFilters(applyDateRange(filters, null))).toBeNull();
  });
});
