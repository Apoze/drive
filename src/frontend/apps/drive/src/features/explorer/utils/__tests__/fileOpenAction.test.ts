import type { Item } from "@/features/drivers/types";
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
  it("opens active WOPI-supported files in a new tab", () => {
    const item = buildItem({ is_wopi_supported: true });
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
