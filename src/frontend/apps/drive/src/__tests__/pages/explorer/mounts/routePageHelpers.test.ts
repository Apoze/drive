import { getParentMountPath } from "@/features/mounts/utils/routePageHelpers";

describe("routePageHelpers", () => {
  it("keeps the mounts index parent path anchored to root", () => {
    expect(getParentMountPath("/")).toBe("/");
  });

  it("drops only the last path segment for nested mount routes", () => {
    expect(getParentMountPath("/reports")).toBe("/");
    expect(getParentMountPath("/reports/2026")).toBe("/reports");
    expect(getParentMountPath("/reports/2026/q1")).toBe("/reports/2026");
  });
});
