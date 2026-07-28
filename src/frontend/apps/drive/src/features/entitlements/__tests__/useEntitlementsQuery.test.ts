import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/Auth";

import { getEntitlements } from "@/utils/entitlements";

import { useEntitlementsQuery } from "../useEntitlementsQuery";

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/utils/entitlements", () => ({
  getEntitlements: jest.fn(),
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedUseAuth = jest.mocked(useAuth);
const mockedGetEntitlements = jest.mocked(getEntitlements);

describe("useEntitlementsQuery", () => {
  beforeEach(() => {
    mockedUseQuery.mockClear();
    mockedUseAuth.mockReset();
    mockedGetEntitlements.mockReset();
  });

  it("keeps the canonical entitlements query contract", async () => {
    mockedUseAuth.mockReturnValue({ user: { id: "user-1" } } as never);
    mockedGetEntitlements.mockResolvedValue({
      can_upload: true,
    } as never);
    mockedUseQuery.mockImplementation((options) => options as never);

    useEntitlementsQuery();

    const queryOptions = mockedUseQuery.mock.calls[0][0] as {
      queryFn: () => Promise<unknown>;
      queryKey: string[];
      enabled: boolean;
      staleTime: number;
    };

    expect(queryOptions.queryKey).toEqual(["entitlements"]);
    expect(queryOptions.enabled).toBe(true);
    expect(queryOptions.staleTime).toBe(60_000);
    await expect(queryOptions.queryFn()).resolves.toEqual({
      can_upload: true,
    });
  });

  it("does not request regular Drive quota for anonymous layouts", () => {
    mockedUseAuth.mockReturnValue({ user: null } as never);
    mockedUseQuery.mockImplementation((options) => options as never);

    useEntitlementsQuery();

    expect(mockedUseQuery.mock.calls[0][0]).toMatchObject({
      queryKey: ["entitlements"],
      enabled: false,
    });
  });
});
