import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MountDiscovery } from "@/features/drivers/types";
import { BrowseExplorerTemplate } from "@/features/explorer/components/shared-browse/BrowseExplorerTemplate";
import { MountsRootBrowseExplorer } from "../MountsRootBrowseExplorer";
import { discoveryToMountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";

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

jest.mock("@/features/mounts/utils/mountExplorerItems", () => ({
  discoveryToMountExplorerItem: jest.fn((mount) => ({
    id: `mount-root:${mount.mount_id}`,
    title: mount.display_name,
    filename: mount.display_name,
    type: "folder",
    path: "/",
    creator: {
      id: "mount",
      full_name: "Mount",
      short_name: "MT",
    },
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2024-01-01T00:00:00Z"),
    description: "",
    created_at: new Date("2024-01-01T00:00:00Z"),
    link_reach: "restricted",
    link_role: "reader",
    abilities: {
      accesses_manage: false,
      accesses_view: false,
      children_create: false,
      children_list: true,
      destroy: false,
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
      restore: false,
      retrieve: true,
      tree: false,
      update: false,
      upload_ended: false,
    },
    mountMeta: {
      mountId: mount.mount_id,
      normalizedPath: "/",
      isMountRoot: true,
    },
  })),
}));

const mockedBrowseExplorerTemplate = jest.mocked(BrowseExplorerTemplate);
const mockedDiscoveryToMountExplorerItem = jest.mocked(discoveryToMountExplorerItem);

describe("MountsRootBrowseExplorer", () => {
  beforeEach(() => {
    mockedBrowseExplorerTemplate.mockClear();
    mockedDiscoveryToMountExplorerItem.mockClear();
  });

  it("routes mounts discovery through the shared browse template", () => {
    const mounts: MountDiscovery[] = [
      {
        mount_id: "mount-1",
        display_name: "Shared Docs",
        provider: "localfs",
        capabilities: { browse: true },
      },
    ];
    const onRetry = jest.fn();

    renderToStaticMarkup(
      <MountsRootBrowseExplorer
        mounts={mounts}
        isLoading={false}
        isError={false}
        onRetry={onRetry}
        getContextMenuItems={jest.fn()}
      />,
    );

    expect(mockedBrowseExplorerTemplate).toHaveBeenCalledTimes(1);
    const props = mockedBrowseExplorerTemplate.mock.calls[0][0];
    expect(props).toEqual(
      expect.objectContaining({
        data: { pages: [mounts] },
        isLoading: false,
        isError: false,
        loadingLabel: "explorer.mounts.loading",
        errorLabel: "explorer.mounts.error",
        onRetry,
        showFilters: false,
        preserveIdleTopBarSpace: true,
        disableItemDragAndDrop: true,
        disableDefaultContextMenu: true,
      }),
    );
    expect(props.mapPageItems(mounts)[0]).toMatchObject({
      title: "Shared Docs",
      filename: "Shared Docs",
      mountMeta: {
        mountId: "mount-1",
        normalizedPath: "/",
        isMountRoot: true,
      },
    });
    expect(mockedDiscoveryToMountExplorerItem).toHaveBeenCalledWith(
      mounts[0],
      0,
      mounts,
    );
  });
});
