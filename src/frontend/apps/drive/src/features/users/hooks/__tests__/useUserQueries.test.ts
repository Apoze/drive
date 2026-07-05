import { useQuery } from "@tanstack/react-query";

import { getDriver } from "@/features/config/Config";

import { useUsers } from "../useUserQueries";

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedGetDriver = jest.mocked(getDriver);

describe("useUsers", () => {
  it("keeps the canonical query key, driver wiring and options merge", async () => {
    const getUsers = jest.fn().mockResolvedValue([{ id: "user-1" }]);
    mockedGetDriver.mockReturnValue({
      getUsers,
    } as never);
    mockedUseQuery.mockImplementation((options) => options as never);

    const filters = { email: "jane@example.test" } as never;
    useUsers(filters, { enabled: false, staleTime: 5000 } as never);

    const queryOptions = mockedUseQuery.mock.calls[0][0] as {
      enabled?: boolean;
      queryFn: () => Promise<unknown>;
      queryKey: unknown[];
      staleTime?: number;
    };

    expect(queryOptions.enabled).toBe(false);
    expect(queryOptions.staleTime).toBe(5000);
    expect(queryOptions.queryKey).toEqual(["users", filters]);
    await expect(queryOptions.queryFn()).resolves.toEqual([{ id: "user-1" }]);
    expect(getUsers).toHaveBeenCalledWith(filters);
  });
});
