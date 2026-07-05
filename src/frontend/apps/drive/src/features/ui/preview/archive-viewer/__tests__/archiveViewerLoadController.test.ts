import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useArchiveViewerLoadController } from "../archiveViewerLoadController";

jest.mock("pretty-bytes", () => ({
  __esModule: true,
  default: (value: number) => `${value} B`,
}));

describe("archiveViewerLoadController", () => {
  it("renders a harness with the current controller snapshot", () => {
    const runtime = {
      loadEntries: jest.fn(),
    };

    const Harness = () => {
      const controller = useArchiveViewerLoadController({
        archiveAccessMode: "auto",
        archiveItem: {
          id: "archive-1",
          mimetype: "application/zip",
          size: 100,
          title: "demo.zip",
          url: undefined,
        },
        runtime: runtime as never,
        t: (key: string) => key,
      });
      return React.createElement(
        "div",
        null,
        `${controller.backend}|${String(controller.loading)}|${String(
          controller.error ?? "",
        )}`,
      );
    };

    const html = renderToStaticMarkup(React.createElement(Harness));

    expect(html).toContain("none|false|");
    expect(runtime.loadEntries).not.toHaveBeenCalled();
  });
});
