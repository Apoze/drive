import { APIError } from "@/features/api/APIError";

import { shouldDisplayGlobalErrorToast } from "../_appRuntime";

describe("_appRuntime", () => {
  it("hides global toasts when the query explicitly disables them", () => {
    expect(
      shouldDisplayGlobalErrorToast(new Error("boom"), {
        meta: { noGlobalError: true },
      } as never),
    ).toBe(false);
  });

  it("hides 401 errors from the global toast layer", () => {
    expect(shouldDisplayGlobalErrorToast(new APIError(401), undefined)).toBe(
      false,
    );
  });

  it("hides 403 errors unless the query opts in", () => {
    expect(
      shouldDisplayGlobalErrorToast(new APIError(403), {
        meta: {},
      } as never),
    ).toBe(false);
    expect(
      shouldDisplayGlobalErrorToast(new APIError(403), {
        meta: { showErrorOn403: true },
      } as never),
    ).toBe(true);
  });

  it("keeps generic runtime errors visible", () => {
    expect(shouldDisplayGlobalErrorToast(new Error("boom"), undefined)).toBe(
      true,
    );
  });
});
