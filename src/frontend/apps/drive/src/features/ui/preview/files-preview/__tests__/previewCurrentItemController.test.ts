import { createPreviewCurrentItemController } from "../previewCurrentItemController";

describe("previewCurrentItemController", () => {
  it("centralizes close and conditional close around the current preview item state", () => {
    const setPreviewCurrentItem = jest.fn();
    const previewItem = { id: "file-1", title: "report.txt" };
    const controller = createPreviewCurrentItemController({
      previewItem,
      setPreviewCurrentItem,
    });

    controller.closePreviewIf((item) => item.id === "other-file");
    controller.closePreviewIf((item) => item.id === previewItem.id);
    controller.closePreview();

    expect(setPreviewCurrentItem).toHaveBeenCalledTimes(2);
    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(1, undefined);
    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(2, undefined);
  });
});
