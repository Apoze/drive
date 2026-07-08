import { useQuery } from "@tanstack/react-query";

import { getDriver } from "@/features/config/Config";

import { useContacts, useUsers } from "../useUserQueries";

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedGetDriver = jest.mocked(getDriver);

describe("user query hooks", () => {
  it("keeps the canonical query key, driver wiring and options merge", async () => {
    const getUsers = jest.fn().mockResolvedValue([{ id: "user-1" }]);
    const getContacts = jest.fn().mockResolvedValue([{ id: "user-2" }]);
    mockedGetDriver.mockReturnValue({
      getUsers,
      getContacts,
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

    useContacts(undefined, { enabled: true } as never);
    const contactsQueryOptions = mockedUseQuery.mock.calls[1][0] as {
      enabled?: boolean;
      queryFn: () => Promise<unknown>;
      queryKey: unknown[];
    };

    expect(contactsQueryOptions.enabled).toBe(true);
    expect(contactsQueryOptions.queryKey).toEqual(["contacts", undefined]);
    await expect(contactsQueryOptions.queryFn()).resolves.toEqual([
      { id: "user-2" },
    ]);
    expect(getContacts).toHaveBeenCalledWith(undefined);
  });
});
