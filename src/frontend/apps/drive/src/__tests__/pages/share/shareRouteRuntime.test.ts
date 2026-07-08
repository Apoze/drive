import { APIError } from "@/features/api/APIError";

import {
  getPublicMountShareError,
  getPublicShareError,
} from "@/features/routing/shareRouteRuntime";

describe("shareRouteRuntime", () => {
  it("classifies item-share errors", () => {
    expect(getPublicShareError(new APIError(404))).toBe("not_found");
    expect(getPublicShareError(new Error("Request timeout exceeded"))).toBe(
      "timeout",
    );
    expect(getPublicShareError(new Error("boom"))).toBe("unknown");
  });

  it("classifies mount-share errors", () => {
    expect(getPublicMountShareError(new APIError(404))).toBe("not_found");
    expect(getPublicMountShareError(new APIError(410))).toBe("gone");
    expect(getPublicMountShareError(new Error("Request timeout exceeded"))).toBe(
      "timeout",
    );
    expect(getPublicMountShareError(new Error("boom"))).toBe("unknown");
  });
});
