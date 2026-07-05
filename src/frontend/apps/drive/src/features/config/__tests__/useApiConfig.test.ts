import { useQuery } from "@tanstack/react-query";

import { getDriver } from "../Config";
import { useApiConfig } from "../useApiConfig";

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
}));

jest.mock("../Config", () => ({
  getDriver: jest.fn(),
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedGetDriver = jest.mocked(getDriver);

describe("useApiConfig", () => {
  it("keeps the canonical config query contract", async () => {
    const getConfig = jest.fn().mockResolvedValue({
      FRONTEND_MORE_LINK: "https://docs.example.test/more",
    });
    mockedGetDriver.mockReturnValue({
      getConfig,
    } as never);
    mockedUseQuery.mockImplementation((options) => options as never);

    useApiConfig();

    const queryOptions = mockedUseQuery.mock.calls[0][0] as {
      queryFn: () => Promise<unknown>;
      queryKey: string[];
      staleTime: number;
    };

    expect(queryOptions.queryKey).toEqual(["config"]);
    expect(queryOptions.staleTime).toBe(1000);
    await expect(queryOptions.queryFn()).resolves.toEqual({
      FRONTEND_MORE_LINK: "https://docs.example.test/more",
    });
  });
});
