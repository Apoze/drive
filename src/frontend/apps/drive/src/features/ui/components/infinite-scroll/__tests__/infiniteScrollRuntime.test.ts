import { shouldFetchNextPage } from "../infiniteScrollRuntime";

describe("shouldFetchNextPage", () => {
  it("returns true only when the sentinel intersects and loading can continue", () => {
    expect(
      shouldFetchNextPage({
        entry: { isIntersecting: true },
        hasNextPage: true,
        isFetchingNextPage: false,
      }),
    ).toBe(true);
  });

  it("returns false when there is no next page", () => {
    expect(
      shouldFetchNextPage({
        entry: { isIntersecting: true },
        hasNextPage: false,
        isFetchingNextPage: false,
      }),
    ).toBe(false);
  });

  it("returns false when a next page is already being fetched", () => {
    expect(
      shouldFetchNextPage({
        entry: { isIntersecting: true },
        hasNextPage: true,
        isFetchingNextPage: true,
      }),
    ).toBe(false);
  });

  it("returns false when the sentinel is not intersecting", () => {
    expect(
      shouldFetchNextPage({
        entry: { isIntersecting: false },
        hasNextPage: true,
        isFetchingNextPage: false,
      }),
    ).toBe(false);
  });
});
