import {
  DEFAULT_OPERATION_TIME_BOUNDS_MS,
  getOperationTimeBound,
  resolveOperationTimeBounds,
} from "../timeBounds";

describe("timeBounds", () => {
  it("merges valid config overrides over the default operation bounds", () => {
    expect(
      resolveOperationTimeBounds({
        FRONTEND_OPERATION_TIME_BOUNDS_MS: {
          config_load: { fail_ms: 2000, still_working_ms: 1000 },
          custom_operation: { fail_ms: 9000, still_working_ms: 4000 },
        },
      }),
    ).toEqual({
      ...DEFAULT_OPERATION_TIME_BOUNDS_MS,
      config_load: { fail_ms: 2000, still_working_ms: 1000 },
      custom_operation: { fail_ms: 9000, still_working_ms: 4000 },
    });
  });

  it("ignores invalid override entries and keeps the default map", () => {
    expect(
      resolveOperationTimeBounds({
        FRONTEND_OPERATION_TIME_BOUNDS_MS: {
          config_load: { fail_ms: -1, still_working_ms: 1000 },
          preview_pdf: { fail_ms: 3000, still_working_ms: "bad" },
        } as never,
      }),
    ).toEqual(DEFAULT_OPERATION_TIME_BOUNDS_MS);
  });

  it("falls back to the canonical default for unknown operations", () => {
    expect(getOperationTimeBound("unknown_operation")).toEqual({
      fail_ms: 20000,
      still_working_ms: 5000,
    });
  });
});
