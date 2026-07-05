import {
  createItemsPreviewController,
} from "../itemsPreviewController";

describe("itemsPreviewController", () => {
  it("exposes explicit open and close operations over the underlying state setters", () => {
    const setPreviewCurrentItem = jest.fn();
    const replacePreviewItems = jest.fn();
    const controller = createItemsPreviewController({
      setPreviewCurrentItem,
      replacePreviewItems,
    });
    const item = { id: "item-1", title: "Report" } as never;
    const siblings = [item, { id: "item-2", title: "Notes" }] as never;

    controller.openPreview(item, siblings);
    controller.openSinglePreview(item);
    controller.closePreview();

    expect(replacePreviewItems).toHaveBeenNthCalledWith(1, siblings);
    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(1, item);
    expect(replacePreviewItems).toHaveBeenNthCalledWith(2, [item]);
    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(2, item);
    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(3, undefined);
  });
});
