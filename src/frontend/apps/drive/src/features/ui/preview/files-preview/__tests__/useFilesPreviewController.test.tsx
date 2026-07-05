import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useFilesPreviewController } from "../useFilesPreviewController";

type TestItem = {
  id: string;
  kind: "file" | "folder";
  label: string;
};

describe("useFilesPreviewController", () => {
  it("centralizes the shared preview glue for previewable files, close, and selection changes", () => {
    const items: TestItem[] = [
      { id: "folder-1", kind: "folder", label: "Docs" },
      { id: "file-1", kind: "file", label: "report.txt" },
      { id: "file-2", kind: "file", label: "plan.txt" },
    ];
    const setPreviewCurrentItem = jest.fn();
    let controller:
      | ReturnType<typeof useFilesPreviewController<TestItem>>
      | undefined;

    const Harness = () => {
      controller = useFilesPreviewController({
        currentItem: items[1],
        items,
        setPreviewCurrentItem,
        isPreviewableItem: (item) => item.kind === "file",
        mapItemToPreviewFile: (item) => ({
          id: item.id,
          filename: item.label,
          title: item.label,
          size: 0,
          mimetype: "text/plain",
        }),
      });

      return null;
    };

    renderToStaticMarkup(<Harness />);

    expect(controller).toBeDefined();
    expect(controller?.isOpen).toBe(true);
    expect(controller?.openedFileId).toBe("file-1");
    expect(controller?.files).toEqual([
      {
        id: "file-1",
        filename: "report.txt",
        title: "report.txt",
        size: 0,
        mimetype: "text/plain",
      },
      {
        id: "file-2",
        filename: "plan.txt",
        title: "plan.txt",
        size: 0,
        mimetype: "text/plain",
      },
    ]);

    controller?.handleChangePreviewItem?.({
      id: "file-2",
      filename: "plan.txt",
      title: "plan.txt",
      size: 0,
      mimetype: "text/plain",
    });
    controller?.handleChangePreviewItem?.();
    controller?.handleClosePreview?.();

    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(1, items[2]);
    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(2, undefined);
    expect(setPreviewCurrentItem).toHaveBeenNthCalledWith(3, undefined);
  });
});
