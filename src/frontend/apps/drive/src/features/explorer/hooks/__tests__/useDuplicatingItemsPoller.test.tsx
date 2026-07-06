import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { getDriver } from "@/features/config/Config";
import { ItemType, ItemUploadState, type Item } from "@/features/drivers/types";
import { useQueries } from "@tanstack/react-query";
import { useRefreshItemCache } from "../useRefreshItems";
import { useDuplicatingItemsPoller } from "../useDuplicatingItemsPoller";

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@tanstack/react-query", () => ({
  useQueries: jest.fn(),
}));

jest.mock("../useRefreshItems", () => ({
  useRefreshItemCache: jest.fn(),
}));

const mockedGetDriver = jest.mocked(getDriver);
const mockedUseQueries = jest.mocked(useQueries);
const mockedUseRefreshItemCache = jest.mocked(useRefreshItemCache);

const buildItem = (
  id: string,
  uploadState: ItemUploadState = ItemUploadState.READY,
): Item =>
  ({
    id,
    title: id,
    filename: `${id}.txt`,
    creator: {
      id: "user-1",
      full_name: "Jane Doe",
      short_name: "JD",
    },
    type: ItemType.FILE,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: uploadState,
    updated_at: new Date("2026-03-23T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-23T00:00:00Z"),
    path: `/${id}.txt`,
    abilities: {},
  }) as Item;

describe("useDuplicatingItemsPoller", () => {
  const refreshItemCache = jest.fn();
  const getItem = jest.fn();

  beforeEach(() => {
    refreshItemCache.mockReset();
    getItem.mockReset();
    mockedUseQueries.mockReset();
    mockedUseRefreshItemCache.mockReturnValue(refreshItemCache);
    mockedGetDriver.mockReturnValue({ getItem } as never);
  });

  it("polls only items in duplicating state and refreshes them once ready", async () => {
    const readyItem = buildItem("copy", ItemUploadState.READY);
    getItem.mockResolvedValueOnce(readyItem);

    const Harness = () => {
      useDuplicatingItemsPoller([
        buildItem("copy", ItemUploadState.DUPLICATING),
        buildItem("regular", ItemUploadState.READY),
      ]);
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const queriesArg = mockedUseQueries.mock.calls[0][0] as {
      queries: Array<{
        queryKey: unknown[];
        queryFn: () => Promise<Item>;
        refetchInterval: (query: {
          state: { data: Item | undefined };
        }) => number | false;
      }>;
    };
    expect(queriesArg.queries).toHaveLength(1);
    expect(queriesArg.queries[0].queryKey).toEqual([
      "items",
      "copy",
      "duplicate-poll",
    ]);

    await expect(queriesArg.queries[0].queryFn()).resolves.toBe(readyItem);

    expect(getItem).toHaveBeenCalledWith("copy");
    expect(refreshItemCache).toHaveBeenCalledWith("copy", readyItem);
    expect(
      queriesArg.queries[0].refetchInterval({ state: { data: readyItem } }),
    ).toBe(false);
  });
});
