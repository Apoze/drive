import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, ItemUploadState, type Item } from "@/features/drivers/types";
import { useDuplicatingItemsPoller } from "../useDuplicatingItemsPoller";
import { useTransientItemsPoller } from "../useTransientItemsPoller";

jest.mock("../useTransientItemsPoller", () => ({
  useTransientItemsPoller: jest.fn(),
}));

const mockedUseTransientItemsPoller = jest.mocked(useTransientItemsPoller);

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
  beforeEach(() => {
    mockedUseTransientItemsPoller.mockReset();
  });

  it("delegates to the shared transient item poller", () => {
    const items = [
      buildItem("copy", ItemUploadState.DUPLICATING),
      buildItem("regular", ItemUploadState.READY),
    ];

    const Harness = () => {
      useDuplicatingItemsPoller(items);
      return null;
    };

    renderToStaticMarkup(<Harness />);

    expect(mockedUseTransientItemsPoller).toHaveBeenCalledWith(items);
  });
});
