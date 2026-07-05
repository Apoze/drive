import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
} from "@/features/drivers/types";
import type { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { createAndCopyMountShareLink } from "@/features/mounts/utils/mountShareLink";
import { MountFilesPreview } from "../MountFilesPreview";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

const renderedButtons: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
}> = [];

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => {
    renderedButtons.push({ children, onClick });
    return <button>{children}</button>;
  },
}));

jest.mock("@/features/ui/preview/files-preview/FilesPreview", () => ({
  FilePreview: ({
    headerRightContent,
    sidebarContent,
  }: {
    headerRightContent?: React.ReactNode;
    sidebarContent?: React.ReactNode;
  }) => (
    <div>
      <div data-testid="preview-header">{headerRightContent}</div>
      <div data-testid="preview-sidebar">{sidebarContent}</div>
    </div>
  ),
}));

jest.mock("@/features/ui/components/info/InfoRow", () => ({
  InfoRow: ({
    label,
    rightContent,
  }: {
    label: React.ReactNode;
    rightContent?: React.ReactNode;
  }) => (
    <div>
      <div>{label}</div>
      <div>{rightContent}</div>
    </div>
  ),
}));

jest.mock("@/features/explorer/utils/utils", () => ({
  formatSize: jest.fn((size: number) => `${size} B`),
}));

jest.mock("@/features/mounts/components/useMountPreviewSource", () => ({
  useMountPreviewSource: jest.fn(() => ({ kind: "mount-preview-source" })),
  itemToMountPreviewFile: jest.fn((item: { id: string; title: string; filename: string }) => ({
    id: item.id,
    title: item.title,
    filename: item.filename,
  })),
}));

jest.mock("@/features/mounts/utils/mountShareLink", () => ({
  createAndCopyMountShareLink: jest.fn(),
}));

const mockedCreateAndCopyMountShareLink = jest.mocked(createAndCopyMountShareLink);

const buildMountItem = (
  shareLinkCreate: boolean,
): MountExplorerItem => ({
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
      move: false,
      rename: false,
      destroy: false,
      upload: false,
      duplicate: false,
      download: true,
      preview: true,
      wopi: false,
      share_link_create: shareLinkCreate,
    },
  },
});

describe("MountFilesPreview", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
    mockedCreateAndCopyMountShareLink.mockReset();
  });

  it("shows a share action for shareable mount preview items and routes it through the shared helper", () => {
    const currentItem = buildMountItem(true);

    const html = renderToStaticMarkup(
      <MountFilesPreview currentItem={currentItem} items={[currentItem]} />,
    );
    const shareButton = renderedButtons.find(
      (button) => button.children === "explorer.rightPanel.share",
    );

    expect(html).toContain("explorer.rightPanel.share");
    expect(shareButton).toBeDefined();

    shareButton?.onClick?.();

    expect(mockedCreateAndCopyMountShareLink).toHaveBeenCalledWith(currentItem);
  });

  it("hides the preview share action when the mount item cannot create share links", () => {
    const currentItem = buildMountItem(false);

    const html = renderToStaticMarkup(
      <MountFilesPreview currentItem={currentItem} items={[currentItem]} />,
    );

    expect(html).not.toContain("explorer.rightPanel.share");
    expect(renderedButtons).toHaveLength(0);
    expect(mockedCreateAndCopyMountShareLink).not.toHaveBeenCalled();
  });
});
