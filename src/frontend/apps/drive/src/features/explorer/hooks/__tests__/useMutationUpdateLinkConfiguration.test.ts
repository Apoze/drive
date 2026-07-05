import { LinkReach, LinkRole } from "@/features/drivers/types";
import { getDriver } from "@/features/config/Config";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMutationUpdateLinkConfiguration } from "../useMutations";

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@tanstack/react-query", () => ({
  useMutation: jest.fn((config) => config),
  useQueryClient: jest.fn(),
}));

jest.mock("../../components/GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
  generateTreeId: jest.fn(),
}));

jest.mock("../useOptimisticPagination", () => ({
  useAddItemToPaginatedList: jest.fn(),
  useRemoveItemsFromPaginatedList: jest.fn(),
}));

jest.mock("../useRefreshItems", () => ({
  useRefreshQueryCacheAfterMutation: jest.fn(),
  useDeleteMutationCallbacks: jest.fn(),
  useRefreshItemCache: jest.fn(),
  useRefreshFavoriteCache: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  useTreeContext: jest.fn(),
}));

const mockedGetDriver = jest.mocked(getDriver);
const mockedUseMutation = jest.mocked(useMutation);
const mockedUseQueryClient = jest.mocked(useQueryClient);

describe("useMutationUpdateLinkConfiguration", () => {
  const invalidateQueries = jest.fn();
  const updateLinkConfiguration = jest.fn();

  beforeEach(() => {
    invalidateQueries.mockReset();
    updateLinkConfiguration.mockReset();
    mockedUseMutation.mockClear();
    mockedGetDriver.mockReturnValue({
      updateLinkConfiguration,
    } as never);
    mockedUseQueryClient.mockReturnValue({
      invalidateQueries,
    } as never);
  });

  it("keeps the driver wiring and invalidates item plus itemAccesses queries", async () => {
    updateLinkConfiguration.mockResolvedValue(undefined);

    const mutation = useMutationUpdateLinkConfiguration() as unknown as {
      mutationFn: (variables: {
        itemId: string;
        link_reach: LinkReach;
        link_role: LinkRole;
      }) => Promise<void>;
      onSuccess: (data: void, variables: {
        itemId: string;
        link_reach: LinkReach;
        link_role: LinkRole;
      }) => void;
    };
    const variables = {
      itemId: "item-1",
      link_reach: LinkReach.PUBLIC,
      link_role: LinkRole.READER,
    };

    await mutation.mutationFn(variables);
    mutation.onSuccess(undefined, variables);

    expect(updateLinkConfiguration).toHaveBeenCalledWith(variables);
    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "item-1"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["itemAccesses"],
    });
  });
});
