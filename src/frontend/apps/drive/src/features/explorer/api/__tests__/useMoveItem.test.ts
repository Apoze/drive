import { getDriver } from "@/features/config/Config";
import { BatchOperationError } from "@/features/errors/BatchOperationError";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMoveItems } from "../useMoveItem";
import { useRemoveItemsFromPaginatedList } from "../../hooks/useOptimisticPagination";
import {
  getMyFilesQueryKey,
  getRecentItemsQueryKey,
  getSharedWithMeQueryKey,
} from "@/utils/defaultRoutes";

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@tanstack/react-query", () => ({
  useMutation: jest.fn((config) => config),
  useQueryClient: jest.fn(),
}));

jest.mock("../../hooks/useOptimisticPagination", () => ({
  useRemoveItemsFromPaginatedList: jest.fn(),
}));

const mockedGetDriver = jest.mocked(getDriver);
const mockedUseMutation = jest.mocked(useMutation);
const mockedUseQueryClient = jest.mocked(useQueryClient);
const mockedUseRemoveItemsFromPaginatedList = jest.mocked(
  useRemoveItemsFromPaginatedList,
);

type MutationConfig<TVariables, TData = unknown, TContext = unknown> = {
  mutationFn: (variables: TVariables) => Promise<TData> | TData;
  onMutate?: (variables: TVariables) => Promise<TContext> | TContext;
  onSuccess?: (
    data: TData,
    variables: TVariables,
    context: TContext,
  ) => void;
  onError?: (error: unknown, variables: TVariables, context: TContext) => void;
  meta?: Record<string, unknown>;
};

describe("useMoveItems", () => {
  const invalidateQueries = jest.fn();
  const cancelQueries = jest.fn();
  const removeItems = jest.fn();
  const driver = {
    moveItems: jest.fn(),
  };

  beforeEach(() => {
    invalidateQueries.mockReset();
    cancelQueries.mockReset();
    cancelQueries.mockResolvedValue(undefined);
    removeItems.mockReset();
    driver.moveItems.mockReset();
    mockedUseMutation.mockClear();
    mockedGetDriver.mockReturnValue(driver as never);
    mockedUseQueryClient.mockReturnValue({
      invalidateQueries,
      cancelQueries,
    } as never);
    mockedUseRemoveItemsFromPaginatedList.mockReturnValue(removeItems);
  });

  it("keeps successful moves local, coherent and out of the global error channel", async () => {
    driver.moveItems.mockResolvedValue(undefined);

    const mutation = useMoveItems() as unknown as MutationConfig<
      {
        ids: string[];
        parentId?: string;
        oldParentId?: string;
      },
      void,
      void
    >;
    const payload = {
      ids: ["item-1", "item-2"],
      parentId: "parent-2",
      oldParentId: "parent-1",
    };

    await mutation.mutationFn(payload);
    await mutation.onMutate?.(payload);
    mutation.onSuccess?.(undefined, payload, undefined);

    expect(driver.moveItems).toHaveBeenCalledWith(["item-1", "item-2"], "parent-2");
    expect(cancelQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "parent-1", "children"],
    });
    expect(cancelQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["items", "parent-2", "children"],
    });
    expect(removeItems).toHaveBeenNthCalledWith(1, ["items", "parent-1"], [
      "item-1",
      "item-2",
    ]);
    expect(removeItems).toHaveBeenNthCalledWith(2, getMyFilesQueryKey(), [
      "item-1",
      "item-2",
    ]);
    expect(removeItems).toHaveBeenNthCalledWith(3, getSharedWithMeQueryKey(), [
      "item-1",
      "item-2",
    ]);
    expect(removeItems).toHaveBeenNthCalledWith(4, getRecentItemsQueryKey(), [
      "item-1",
      "item-2",
    ]);
    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "parent-1"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["items", "parent-2"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(3, {
      queryKey: getMyFilesQueryKey(),
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(4, {
      queryKey: getSharedWithMeQueryKey(),
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(5, {
      queryKey: getRecentItemsQueryKey(),
    });
    expect(mutation.meta).toEqual({
      showErrorOn403: true,
      noGlobalError: true,
    });
  });

  it("keeps partial move failures honest by removing only confirmed ids locally", () => {
    const mutation = useMoveItems() as unknown as MutationConfig<
      {
        ids: string[];
        parentId?: string;
        oldParentId?: string;
      },
      void,
      void
    >;
    const payload = {
      ids: ["item-1", "item-2"],
      parentId: "parent-2",
      oldParentId: "parent-1",
    };

    mutation.onError?.(
      new BatchOperationError({
        completedIds: ["item-1"],
        failedId: "item-2",
        cause: new Error("403"),
      }),
      payload,
      undefined,
    );

    expect(removeItems).toHaveBeenNthCalledWith(1, ["items", "parent-1"], [
      "item-1",
    ]);
    expect(removeItems).toHaveBeenNthCalledWith(2, getMyFilesQueryKey(), [
      "item-1",
    ]);
    expect(removeItems).toHaveBeenNthCalledWith(3, getSharedWithMeQueryKey(), [
      "item-1",
    ]);
    expect(removeItems).toHaveBeenNthCalledWith(4, getRecentItemsQueryKey(), [
      "item-1",
    ]);
    expect(invalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: ["items", "parent-1"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: ["items", "parent-2"],
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(3, {
      queryKey: getMyFilesQueryKey(),
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(4, {
      queryKey: getSharedWithMeQueryKey(),
    });
    expect(invalidateQueries).toHaveBeenNthCalledWith(5, {
      queryKey: getRecentItemsQueryKey(),
    });
  });
});
