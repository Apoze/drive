import { docsCreationUrl } from "../docsNavigation";
import type { Item } from "@/features/drivers/types";
import { ItemType } from "@/features/drivers/types";
import {
  openFileFromExplorer,
  resolveExplorerFileOpenAction,
} from "../fileOpenAction";

const buildItem = (overrides: Partial<Item> = {}): Item =>
  ({
    id: "item-1",
    url: "https://example.test/file",
    ...overrides,
  }) as Item;

describe("fileOpenAction", () => {
  it("carries only the selected destination to Docs creation", () => {
    const url = new URL(
      docsCreationUrl(
        "https://docs.example.test/?unused=1#old",
        "folder",
        "space",
      )!,
    );
    expect(url.pathname).toBe("/docs/new/");
    expect(url.searchParams.get("drive_destination")).toBe("folder");
    expect(url.searchParams.get("drive_space_id")).toBe("space");
    expect(url.searchParams.has("unused")).toBe(false);
    expect(url.hash).toBe("");
    expect(docsCreationUrl("javascript:alert(1)", "folder")).toBeUndefined();
    expect(
      docsCreationUrl("https://user:password@example.test", "folder"),
    ).toBeUndefined();
    expect(
      docsCreationUrl("https://docs.example.test", undefined),
    ).toBeUndefined();
  });
  it("opens native documents without entering any binary viewer", () => {
    const item = buildItem({
      type: ItemType.DOCS,
      document: {
        id: "doc-1",
        state: "active",
        revision: 1,
        url: "https://docs.example.test/docs/doc-1/",
      },
      abilities: { open_docs: true } as Item["abilities"],
      is_wopi_supported: true,
    });
    const open = jest.fn();
    const openPreview = jest.fn();
    const openWopi = jest.fn();
    openFileFromExplorer({ item, openPreview, openWopi, openDocs: open });
    expect(open).toHaveBeenCalledWith(item.document?.url);
    expect(openPreview).not.toHaveBeenCalled();
    expect(openWopi).not.toHaveBeenCalled();
    expect(
      resolveExplorerFileOpenAction({
        item: { ...item, deleted_at: new Date() },
      }),
    ).toEqual({ type: "preview-unavailable" });
    expect(
      resolveExplorerFileOpenAction({
        item: {
          ...item,
          document: { ...item.document!, url: "javascript:alert(1)" },
        },
      }),
    ).toEqual({ type: "preview-unavailable" });
  });
  it("opens active WOPI-supported files in a new tab", () => {
    const item = buildItem({
      filename: "notes.txt",
      mimetype: "text/plain",
      title: "notes.txt",
      is_wopi_supported: true,
    });
    const openWopi = jest.fn();
    const openPreview = jest.fn();

    openFileFromExplorer({
      item,
      openPreview,
      openWopi,
    });

    expect(resolveExplorerFileOpenAction({ item })).toEqual({
      type: "wopi-new-tab",
      itemId: item.id,
    });
    expect(openWopi).toHaveBeenCalledWith(item.id);
    expect(openPreview).not.toHaveBeenCalled();
  });

  it("keeps allowlisted text files in preview when WOPI also supports them", () => {
    const item = buildItem({
      filename: "oemsetup.inf",
      mimetype: "text/plain",
      title: "oemsetup.inf",
      is_wopi_supported: true,
    });
    const openWopi = jest.fn();
    const openPreview = jest.fn();

    openFileFromExplorer({
      item,
      openPreview,
      openWopi,
    });

    expect(resolveExplorerFileOpenAction({ item })).toEqual({
      type: "preview",
    });
    expect(openPreview).toHaveBeenCalledWith(item);
    expect(openWopi).not.toHaveBeenCalled();
  });

  it("keeps extensionless text files in WOPI", () => {
    const item = buildItem({
      mimetype: "text/plain",
      title: "Budget report",
      is_wopi_supported: true,
    });

    expect(resolveExplorerFileOpenAction({ item })).toEqual({
      type: "wopi-new-tab",
      itemId: item.id,
    });
  });

  it("keeps deleted WOPI-supported files in the preview flow", () => {
    const item = buildItem({
      deleted_at: new Date("2026-03-22T00:00:00Z"),
      is_wopi_supported: true,
    });
    const openWopi = jest.fn();
    const openPreview = jest.fn();

    openFileFromExplorer({
      item,
      openPreview,
      openWopi,
    });

    expect(resolveExplorerFileOpenAction({ item })).toEqual({
      type: "preview",
    });
    expect(openPreview).toHaveBeenCalledWith(item);
    expect(openWopi).not.toHaveBeenCalled();
  });

  it("opens non-WOPI files through preview", () => {
    const item = buildItem({ is_wopi_supported: false });
    const openPreview = jest.fn();

    openFileFromExplorer({
      item,
      openPreview,
    });

    expect(openPreview).toHaveBeenCalledWith(item);
  });

  it("reports preview-unavailable when a caller requires a file URL", () => {
    const item = buildItem({ url: undefined });
    const openPreview = jest.fn();
    const onPreviewUnavailable = jest.fn();

    openFileFromExplorer({
      item,
      requirePreviewUrl: true,
      openPreview,
      onPreviewUnavailable,
    });

    expect(
      resolveExplorerFileOpenAction({
        item,
        requirePreviewUrl: true,
      }),
    ).toEqual({
      type: "preview-unavailable",
    });
    expect(onPreviewUnavailable).toHaveBeenCalled();
    expect(openPreview).not.toHaveBeenCalled();
  });
});
