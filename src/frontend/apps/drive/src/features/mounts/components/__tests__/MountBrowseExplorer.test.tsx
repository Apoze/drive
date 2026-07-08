import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
} from "@/features/drivers/types";
import { BrowseExplorerTemplate } from "@/features/explorer/components/shared-browse/BrowseExplorerTemplate";
import type { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { MountBrowseExplorer } from "../MountBrowseExplorer";
import { useMountActionController } from "../useMountActionController";
import { useMountUploadController } from "../useMountUploadController";

const capturedShellMenuOptions: Array<{ label?: React.ReactNode }> = [];

jest.mock("@tanstack/react-query", () => ({
  useInfiniteQuery: jest.fn(),
  useQuery: jest.fn(),
}));

jest.mock("next/router", () => ({
  useRouter: () => ({
    query: {
      mount_id: "mount-1",
      path: "/docs",
    },
    push: jest.fn(),
  }),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(() => ({
    getMountsDiscovery: jest.fn(),
    browseMount: jest.fn(),
  })),
}));

jest.mock("@/features/mounts/utils/mountExplorerItems", () => ({
  entryToMountExplorerItem: jest.fn((mountId: string, entry: { normalized_path: string; name: string; entry_type: string }) => ({
    id: `mount-entry:${mountId}:${entry.normalized_path}`,
    title: entry.name,
    filename: entry.name,
    type: entry.entry_type,
    path: entry.normalized_path,
    mountMeta: {
      mountId,
      normalizedPath: entry.normalized_path,
      entryType: entry.entry_type,
      mountTitle: "Shared Docs",
      provider: "localfs",
      abilities: {
        children_list: false,
        create_folder: false,
        move: true,
        rename: true,
        destroy: true,
        upload: false,
        duplicate: true,
        download: true,
        preview: true,
        wopi: true,
        share_link_create: true,
      },
    },
  })),
  getMountTitle: jest.fn((mount: { display_name: string; mount_id: string }) =>
    mount.display_name || mount.mount_id,
  ),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({ children }: { children?: React.ReactNode }) => <button>{children}</button>,
  useModal: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  ContextMenu: ({
    children,
    options,
  }: {
    children?: React.ReactNode;
    options?: Array<{ label?: React.ReactNode }>;
  }) => {
    capturedShellMenuOptions.splice(
      0,
      capturedShellMenuOptions.length,
      ...(options ?? []),
    );
    return <div data-options-count={options?.length ?? 0}>{children}</div>;
  },
  DropdownMenu: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  useDropdownMenu: () => ({
    isOpen: false,
    setIsOpen: jest.fn(),
  }),
}));

jest.mock(
  "@/features/explorer/components/shared-browse/BrowseExplorerTemplate",
  () => ({
    BrowseExplorerTemplate: jest.fn(({ renderAfterExplorer, ...props }) => (
      <div>
        <div>browse-template</div>
        <div>{String(Boolean(props.selectionBarActions))}</div>
        {renderAfterExplorer?.([
          {
            id: "child-item",
            title: "child.txt",
            filename: "child.txt",
            type: "file",
          },
        ])}
      </div>
    )),
  }),
);

jest.mock("@/features/mounts/components/MountExplorerBreadcrumbs", () => ({
  MountExplorerBreadcrumbs: () => <div>mount-breadcrumbs</div>,
}));

jest.mock("@/features/mounts/components/MountFilesPreview", () => ({
  MountFilesPreview: jest.fn(() => <div>mount-preview</div>),
}));

jest.mock("@/features/mounts/components/MountCreateFolderModal", () => ({
  MountCreateFolderModal: jest.fn(() => <div>create-folder-modal</div>),
}));

jest.mock("@/features/mounts/components/MountRenameModal", () => ({
  MountRenameModal: jest.fn(() => <div>rename-modal</div>),
}));

jest.mock("@/features/mounts/components/MountMoveModal", () => ({
  MountMoveModal: jest.fn(() => <div>move-modal</div>),
}));

jest.mock("@/features/mounts/components/MountDeleteModal", () => ({
  MountDeleteModal: jest.fn(() => <div>delete-modal</div>),
}));

jest.mock("@/features/mounts/components/useMountActionController", () => ({
  useMountActionController: jest.fn(),
}));

jest.mock("@/features/mounts/components/useMountUploadController", () => ({
  useMountUploadController: jest.fn(),
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedUseInfiniteQuery = jest.mocked(useInfiniteQuery);
const mockedUseModal = jest.mocked(useModal);
const mockedBrowseExplorerTemplate = jest.mocked(BrowseExplorerTemplate);
const mockedUseMountActionController = jest.mocked(useMountActionController);
const mockedUseMountUploadController = jest.mocked(useMountUploadController);

const selectionBarActions = <div>selection-actions</div>;
const mountDropZone = {} as never;

const actionItem: MountExplorerItem = {
  id: "mount-entry:mount-1:/docs/report.txt",
  title: "report.txt",
  filename: "report.txt",
  creator: {
    id: "mount",
    full_name: "Mount",
    short_name: "MT",
  },
  type: ItemType.FILE,
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: null,
  computed_link_role: null,
  upload_state: ItemUploadState.READY,
  updated_at: new Date("2026-03-22T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-22T00:00:00Z"),
  path: "/docs/report.txt",
  url: "http://example.test/download",
  mimetype: "text/plain",
  link_reach: LinkReach.RESTRICTED,
  link_role: LinkRole.READER,
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
    move: true,
    link_select_options: {
      [LinkReach.RESTRICTED]: null,
      [LinkReach.AUTHENTICATED]: null,
      [LinkReach.PUBLIC]: null,
    },
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: false,
    update: true,
    upload_ended: false,
  },
  mountMeta: {
    mountId: "mount-1",
    normalizedPath: "/docs/report.txt",
    entryType: "file",
    mountTitle: "Shared Docs",
    provider: "localfs",
    abilities: {
      children_list: false,
      create_folder: false,
      move: true,
      rename: true,
      destroy: true,
      upload: false,
      duplicate: true,
      download: true,
      preview: true,
      wopi: true,
      share_link_create: true,
    },
  },
};

describe("MountBrowseExplorer", () => {
  beforeEach(() => {
    capturedShellMenuOptions.length = 0;
    mockedBrowseExplorerTemplate.mockClear();
    mockedUseMountActionController.mockReset();
    mockedUseMountUploadController.mockReset();
    mockedUseModal.mockReset();
    mockedUseQuery.mockReset();
    mockedUseInfiniteQuery.mockReset();

    mockedUseModal
      .mockReturnValueOnce({
        isOpen: true,
        open: jest.fn(),
        close: jest.fn(),
      } as never)
      .mockReturnValueOnce({
        isOpen: true,
        open: jest.fn(),
        close: jest.fn(),
      } as never)
      .mockReturnValueOnce({
        isOpen: true,
        open: jest.fn(),
        close: jest.fn(),
      } as never)
      .mockReturnValueOnce({
        isOpen: true,
        open: jest.fn(),
        close: jest.fn(),
      } as never);

    mockedUseQuery.mockReturnValue({
      data: [
        {
          mount_id: "mount-1",
          display_name: "Shared Docs",
          provider: "localfs",
          capabilities: { browse: true },
        },
      ],
    } as never);

    mockedUseInfiniteQuery.mockReturnValue({
      data: {
        pages: [
          {
            normalized_path: "/docs",
            capabilities: {
              "mount.upload": true,
              "mount.create_folder": true,
            },
            entry: {
              entry_type: "folder",
              abilities: {
                children_list: true,
                create_folder: true,
                move: true,
                rename: true,
                destroy: true,
                upload: true,
                duplicate: false,
                download: false,
                preview: false,
                wopi: false,
                share_link_create: true,
              },
            },
            children: {
              count: 1,
              results: [
                {
                  mount_id: "mount-1",
                  normalized_path: "/docs/report.txt",
                  entry_type: "file",
                  name: "report.txt",
                  size: 12,
                  modified_at: "2026-03-22T00:00:00Z",
                  abilities: {
                    children_list: false,
                    create_folder: false,
                    move: true,
                    rename: true,
                    destroy: true,
                    upload: false,
                    duplicate: true,
                    download: true,
                    preview: true,
                    wopi: true,
                    share_link_create: true,
                  },
                },
              ],
            },
          },
        ],
      },
      isLoading: false,
      isError: false,
      hasNextPage: false,
      isFetchingNextPage: false,
      fetchNextPage: jest.fn(),
      refetch: jest.fn(),
    } as never);

    mockedUseMountActionController.mockReturnValue({
      previewItem: actionItem,
      setPreviewCurrentItem: jest.fn(),
      openPreview: jest.fn(),
      closePreview: jest.fn(),
      actionItems: [actionItem],
      activeActionItem: actionItem,
      clearActionItems: jest.fn(),
      selectionBarActions,
      getContextMenuItems: jest.fn(() => [
        { label: "explorer.mounts.actions.preview" },
      ]),
      handleNavigate: jest.fn(),
      handleFileClick: jest.fn(),
      handleCreateFolderSelection: jest.fn(),
      handleRenameRequest: jest.fn(),
      handleMoveRequest: jest.fn(),
      handleDeleteRequest: jest.fn(),
      handleRenameSuccess: jest.fn(),
      handleMoveSuccess: jest.fn(),
      handleDeleteSuccess: jest.fn(),
    });

    mockedUseMountUploadController.mockReturnValue({
      uploadLoading: false,
      mountDropZone,
      mountImportInputs: <div>mount-import-inputs</div>,
      importMenuItems: [
        {
          label: "explorer.tree.import.files",
          callback: jest.fn(),
        },
      ],
    });
  });

  it("delegates browse wiring to the extracted mounts controllers", () => {
    renderToStaticMarkup(<MountBrowseExplorer />);

    expect(mockedUseMountActionController).toHaveBeenCalledWith({
      mountId: "mount-1",
      mountTitle: "Shared Docs",
      provider: "localfs",
      normalizedPath: "/docs",
      onBrowseRefetch: expect.any(Function),
    });

    expect(mockedUseMountUploadController).toHaveBeenCalledWith({
      mountId: "mount-1",
      browse: expect.objectContaining({
        normalized_path: "/docs",
      }),
      canUploadCurrentFolder: true,
      canImportFoldersCurrentFolder: true,
      onBrowseRefetch: expect.any(Function),
    });

    expect(mockedBrowseExplorerTemplate).toHaveBeenCalledTimes(1);
    const props = mockedBrowseExplorerTemplate.mock.calls[0][0];
    expect(props).toEqual(
      expect.objectContaining({
        isLoading: false,
        isError: false,
        selectionBarActions,
        dropZone: mountDropZone,
        disableDefaultContextMenu: true,
        preserveIdleTopBarSpace: true,
      }),
    );
    expect(typeof props.onNavigate).toBe("function");
    expect(typeof props.onFileClick).toBe("function");
    expect(typeof props.getContextMenuItems).toBe("function");
    expect(typeof props.renderAfterExplorer).toBe("function");
  });

  it("uses the mount id as a provider-agnostic fallback while discovery is loading", () => {
    mockedUseQuery.mockReturnValue({
      data: [],
    } as never);

    renderToStaticMarkup(<MountBrowseExplorer />);

    expect(mockedUseMountActionController).toHaveBeenCalledWith(
      expect.objectContaining({
        mountTitle: "mount-1",
        provider: undefined,
      }),
    );
  });

  it("keeps preview and modal wiring intact after controller extraction", () => {
    const html = renderToStaticMarkup(<MountBrowseExplorer />);

    expect(html).toContain("mount-import-inputs");
    expect(html).toContain("mount-preview");
    expect(html).toContain("create-folder-modal");
    expect(html).toContain("rename-modal");
    expect(html).toContain("move-modal");
    expect(html).toContain("delete-modal");
  });

  it("keeps create folder before import actions in the shell context menu", () => {
    renderToStaticMarkup(<MountBrowseExplorer />);

    const visibleLabels = capturedShellMenuOptions.flatMap((option) =>
      option.label ? [String(option.label)] : [],
    );

    expect(visibleLabels).toEqual([
      "explorer.actions.createFolder.modal.title",
      "explorer.tree.import.files",
    ]);
  });
});
