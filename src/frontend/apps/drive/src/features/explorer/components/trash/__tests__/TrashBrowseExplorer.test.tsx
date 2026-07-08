import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useQuery } from "@tanstack/react-query";
import { Item, ItemType } from "@/features/drivers/types";
import { BrowseExplorerTemplate } from "@/features/explorer/components/shared-browse/BrowseExplorerTemplate";
import { TrashBrowseExplorer } from "../TrashBrowseExplorer";

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(() => ({
    getTrashItems: jest.fn(),
  })),
}));

jest.mock(
  "@/features/explorer/components/shared-browse/BrowseExplorerTemplate",
  () => ({
    BrowseExplorerTemplate: jest.fn(() => <div>browse-template</div>),
  }),
);

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedBrowseExplorerTemplate = jest.mocked(BrowseExplorerTemplate);

const makeItem = (id: string): Item =>
  ({
    id,
    title: id,
    filename: `${id}.txt`,
    creator: {
      id: "tester",
      full_name: "Tester",
      short_name: "TS",
    },
    type: ItemType.FILE,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2024-01-01T00:00:00Z"),
    description: "",
    created_at: new Date("2024-01-01T00:00:00Z"),
    path: `/${id}.txt`,
    link_reach: "restricted",
    link_role: "reader",
    abilities: {
      accesses_manage: false,
      accesses_view: false,
      children_create: false,
      children_list: false,
      destroy: true,
      favorite: false,
      invite_owner: false,
      link_configuration: false,
      media_auth: false,
      move: false,
      link_select_options: {
        restricted: null,
        authenticated: null,
        public: null,
      },
      partial_update: false,
      restore: true,
      retrieve: true,
      tree: false,
      update: false,
      upload_ended: false,
    },
  }) as Item;

describe("TrashBrowseExplorer", () => {
  beforeEach(() => {
    mockedUseQuery.mockReset();
    mockedBrowseExplorerTemplate.mockClear();
  });

  it("routes trash browse through the shared browse template", () => {
    const trashItems = [makeItem("deleted-file")];
    const gridActionsCell = jest.fn();
    const onNavigate = jest.fn();
    const onFileClick = jest.fn();

    mockedUseQuery.mockReturnValue({
      data: trashItems,
      isLoading: false,
      isError: false,
      refetch: jest.fn(),
    } as never);

    renderToStaticMarkup(
      <TrashBrowseExplorer
        gridActionsCell={gridActionsCell}
        gridHeader={<div>trash-header</div>}
        selectionBarActions={<div>trash-selection</div>}
        onNavigate={onNavigate}
        onFileClick={onFileClick}
      />,
    );

    expect(mockedBrowseExplorerTemplate).toHaveBeenCalledTimes(1);
    const props = mockedBrowseExplorerTemplate.mock.calls[0][0];
    expect(props).toEqual(
      expect.objectContaining({
        data: { pages: [trashItems] },
        isLoading: false,
        isError: false,
        loadingLabel: "explorer.trash.loading",
        errorLabel: "explorer.trash.error",
        disableItemDragAndDrop: true,
        gridActionsCell,
        onNavigate,
        onFileClick,
      }),
    );
    expect(props.mapPageItems(trashItems)).toBe(trashItems);
  });
});
