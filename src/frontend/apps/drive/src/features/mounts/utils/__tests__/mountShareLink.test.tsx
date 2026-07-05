import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, ItemUploadState, LinkReach, LinkRole } from "@/features/drivers/types";
import { createAndCopyMountShareLink } from "../mountShareLink";
import { getDriver } from "@/features/config/Config";
import { writeTextToClipboard } from "@/hooks/useCopyToClipboard";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import type { MountExplorerItem } from "../mountExplorerItems";

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@/hooks/useCopyToClipboard", () => ({
  writeTextToClipboard: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock("@/features/api/APIError", () => ({
  errorToString: (error: unknown) => `ERR:${String(error)}`,
}));

const mockedGetDriver = jest.mocked(getDriver);
const mockedWriteTextToClipboard = jest.mocked(writeTextToClipboard);
const mockedAddToast = jest.mocked(addToast);

const mountItem: MountExplorerItem = {
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

describe("createAndCopyMountShareLink", () => {
  beforeEach(() => {
    mockedGetDriver.mockReset();
    mockedWriteTextToClipboard.mockReset();
    mockedAddToast.mockReset();
  });

  it("creates the share link, copies it, and toasts the url", async () => {
    mockedGetDriver.mockReturnValue({
      createMountShareLink: jest.fn().mockResolvedValue({
        share_url: "https://share.example.test/mount-1",
      }),
    } as never);
    mockedWriteTextToClipboard.mockResolvedValue(undefined);

    await createAndCopyMountShareLink(mountItem);

    expect(mockedGetDriver().createMountShareLink).toHaveBeenCalledWith({
      mountId: "mount-1",
      path: "/docs/report.txt",
    });
    expect(mockedWriteTextToClipboard).toHaveBeenCalledWith(
      "https://share.example.test/mount-1",
    );
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement)).toContain(
      "https://share.example.test/mount-1",
    );
  });

  it("keeps the url visible when clipboard copy fails", async () => {
    mockedGetDriver.mockReturnValue({
      createMountShareLink: jest.fn().mockResolvedValue({
        share_url: "https://share.example.test/mount-1",
      }),
    } as never);
    mockedWriteTextToClipboard.mockRejectedValue(new Error("clipboard unavailable"));

    await createAndCopyMountShareLink(mountItem);

    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement)).toContain(
      "https://share.example.test/mount-1",
    );
  });

  it("toasts the API error when link creation fails", async () => {
    mockedGetDriver.mockReturnValue({
      createMountShareLink: jest.fn().mockRejectedValue("boom"),
    } as never);

    await createAndCopyMountShareLink(mountItem);

    expect(mockedWriteTextToClipboard).not.toHaveBeenCalled();
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement)).toContain(
      "ERR:boom",
    );
  });
});
