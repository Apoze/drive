import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
} from "@/features/drivers/types";
import { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { MountTreeItemActions } from "../MountTreeItemActions";
import { useGlobalExplorer } from "../../GlobalExplorerContext";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

const capturedDropdownOptions: Array<{
  label?: React.ReactNode;
  callback?: () => void;
}> = [];

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({ children }: { children?: React.ReactNode }) => (
    <button>{children}</button>
  ),
  useModal: () => ({
    isOpen: false,
    open: jest.fn(),
    close: jest.fn(),
  }),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  DropdownMenu: ({
    options,
    children,
  }: {
    options: Array<{ label?: React.ReactNode; callback?: () => void }>;
    children: React.ReactNode;
  }) => {
    capturedDropdownOptions.splice(0, capturedDropdownOptions.length, ...options);
    return <div>{children}</div>;
  },
  useTreeContext: () => ({
    treeData: {
      deleteNode: jest.fn(),
      getNode: jest.fn(),
      addChild: jest.fn(),
    },
  }),
}));

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

jest.mock("../../../utils/utils", () => ({
  setFromRoute: jest.fn(),
}));

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: jest.fn(),
  }),
}));

jest.mock("../../GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("@/features/mounts/components/MountMoveModal", () => ({
  MountMoveModal: () => null,
}));

jest.mock("@/features/mounts/components/MountRenameModal", () => ({
  MountRenameModal: () => null,
}));

jest.mock("@/features/mounts/components/MountDeleteModal", () => ({
  MountDeleteModal: () => null,
}));

jest.mock("@/features/mounts/utils/mountShareLink", () => ({
  createAndCopyMountShareLink: jest.fn(),
}));

const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);

const buildMountItem = (): MountExplorerItem => ({
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
    destroy: false,
    favorite: false,
    invite_owner: false,
    link_configuration: false,
    media_auth: false,
    move: false,
    link_select_options: {
      [LinkReach.RESTRICTED]: null,
      [LinkReach.AUTHENTICATED]: null,
      [LinkReach.PUBLIC]: null,
    },
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: false,
    update: false,
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
      duplicate: false,
      download: true,
      preview: true,
      wopi: false,
      share_link_create: true,
    },
  },
});

describe("MountTreeItemActions", () => {
  beforeEach(() => {
    capturedDropdownOptions.length = 0;
  });

  it("routes the info action through the explicit right-panel API", () => {
    const openRightPanelForItem = jest.fn();
    const item = buildMountItem();

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem,
      replaceRightPanelItemIfCurrent: jest.fn(),
      closeRightPanelIfCurrent: jest.fn(),
    } as never);

    renderToStaticMarkup(<MountTreeItemActions item={item} />);

    const infoAction = capturedDropdownOptions.find(
      (action) => action.label === "explorer.item.actions.view_info",
    );

    infoAction?.callback?.();

    expect(infoAction).toBeDefined();
    expect(openRightPanelForItem).toHaveBeenCalledWith(item);
  });

  it("keeps the tree dropdown aligned with the converged mount action order", () => {
    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      replaceRightPanelItemIfCurrent: jest.fn(),
      closeRightPanelIfCurrent: jest.fn(),
    } as never);

    renderToStaticMarkup(<MountTreeItemActions item={buildMountItem()} />);

    const visibleLabels = capturedDropdownOptions.flatMap((action) =>
      action.label ? [String(action.label)] : [],
    );

    expect(visibleLabels).toEqual([
      "explorer.mounts.actions.share",
      "explorer.item.actions.rename",
      "explorer.item.actions.move",
      "explorer.item.actions.view_info",
      "explorer.item.actions.delete",
    ]);
  });
});
