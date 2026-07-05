import { useQuery } from "@tanstack/react-query";

import { getEntitlements } from "@/utils/entitlements";

import { useEntitlementsQuery } from "../useEntitlementsQuery";

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
}));

jest.mock("@/utils/entitlements", () => ({
  getEntitlements: jest.fn(),
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedGetEntitlements = jest.mocked(getEntitlements);

describe("useEntitlementsQuery", () => {
  it("keeps the canonical entitlements query contract", async () => {
    mockedGetEntitlements.mockResolvedValue({
      can_upload: true,
    } as never);
    mockedUseQuery.mockImplementation((options) => options as never);

    useEntitlementsQuery();

    const queryOptions = mockedUseQuery.mock.calls[0][0] as {
      queryFn: () => Promise<unknown>;
      queryKey: string[];
      staleTime: number;
    };

    expect(queryOptions.queryKey).toEqual(["entitlements"]);
    expect(queryOptions.staleTime).toBe(60_000);
    await expect(queryOptions.queryFn()).resolves.toEqual({
      can_upload: true,
    });
  });
});
