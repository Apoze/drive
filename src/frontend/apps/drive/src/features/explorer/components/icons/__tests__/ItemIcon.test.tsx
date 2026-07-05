import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  FileIcon,
  FolderIcon,
  ItemIcon,
  WorkspaceIcon,
  getIconByMimeType,
  getItemIcon,
} from "../ItemIcon";

jest.mock("../../../utils/mimeTypes", () => ({
  getItemMimeCategory: jest.fn((item: { title: string }) =>
    item.title.includes("sheet") ? "calc" : "doc",
  ),
  getMimeCategory: jest.fn((mimeType: string, extension?: string) =>
    mimeType === "text/csv" || extension === "csv" ? "calc" : "doc",
  ),
  ICONS: {
    normal: {
      calc: { src: "calc-normal.svg" },
      doc: { src: "doc-normal.svg" },
    },
    mini: {
      calc: { src: "calc-mini.svg" },
      doc: { src: "doc-mini.svg" },
    },
  },
}));

jest.mock("../../../utils/utils", () => ({
  getExtensionFromName: (value: string) => {
    const parts = value.split(".");
    return parts.length > 1 ? parts.pop() : null;
  },
}));

jest.mock("@/assets/folder/folder.svg", () => ({
  __esModule: true,
  default: { src: "folder.svg" },
}));

jest.mock("@/assets/tree/folder.svg", () => ({
  __esModule: true,
  default: { src: "folder-tree.svg" },
}));

jest.mock("@/assets/folder/folder-tiny-perso.svg", () => ({
  __esModule: true,
  default: { src: "folder-personal.svg" },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  getContainerSize: jest.fn(() => 24),
  getIconSize: jest.fn(() => 16),
  Icon: ({ name }: { name: string }) => <span>{name}</span>,
  IconSize: {
    MEDIUM: "medium",
  },
}));

const buildItem = (overrides: Record<string, unknown> = {}) =>
  ({
    id: "item-1",
    title: "demo.docx",
    filename: "demo.docx",
    type: "file",
    creator: {
      id: "user-1",
      full_name: "Jane Doe",
      short_name: "JD",
    },
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-23T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-23T00:00:00Z"),
    path: "/demo.docx",
    abilities: {
      accesses_manage: false,
      accesses_view: true,
      children_create: false,
      children_list: false,
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
    ...overrides,
  }) as never;

describe("ItemIcon family", () => {
  it("keeps item/file icon resolution stable for folders, trees and mime categories", () => {
    expect(getItemIcon(buildItem({ type: "folder" }), "normal", false)).toEqual(
      expect.objectContaining({
        src: expect.any(String),
      }),
    );
    expect(getItemIcon(buildItem({ type: "folder" }), "normal", true)).toEqual(
      expect.objectContaining({
        src: expect.any(String),
      }),
    );
    expect(getItemIcon(buildItem({ title: "sheet.csv" }), "mini", false)).toEqual({
      src: "calc-mini.svg",
    });

    expect(getIconByMimeType("text/csv", "normal", "sheet.csv")).toEqual({
      src: "calc-normal.svg",
    });

    const itemIconHtml = renderToStaticMarkup(
      <ItemIcon item={buildItem()} size={"medium" as never} type="normal" />,
    );
    const fileIconHtml = renderToStaticMarkup(
      <FileIcon
        file={{
          id: "file-1",
          size: 10,
          title: "sheet.csv",
          filename: "sheet.csv",
          mimetype: "text/csv",
        }}
        size="large"
      />,
    );

    expect(itemIconHtml).toContain("src=\"doc-normal.svg\"");
    expect(itemIconHtml).toContain("width=\"16\"");
    expect(fileIconHtml).toContain("src=\"calc-normal.svg\"");
    expect(fileIconHtml).toContain("class=\"item-icon large\"");
  });

  it("keeps workspace and folder surfaces stable", () => {
    const mainWorkspaceHtml = renderToStaticMarkup(
      <WorkspaceIcon isMainWorkspace={true} />,
    );
    const sharedWorkspaceHtml = renderToStaticMarkup(
      <WorkspaceIcon isMainWorkspace={false} />,
    );
    const folderHtml = renderToStaticMarkup(<FolderIcon />);

    expect(mainWorkspaceHtml).toContain("src=\"folder-personal.svg\"");
    expect(sharedWorkspaceHtml).toContain("workspace-icon-container");
    expect(sharedWorkspaceHtml).toContain("groups");
    expect(folderHtml).toContain("draggable=\"false\"");
    expect(folderHtml).toContain("width=\"24\"");
  });
});
