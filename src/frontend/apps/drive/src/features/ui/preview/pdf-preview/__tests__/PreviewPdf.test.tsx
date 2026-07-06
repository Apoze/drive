import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PreviewPdf } from "../PreviewPdf";

const mockDocumentProps: Array<{
  file?: unknown;
  options?: Record<string, unknown>;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("react-pdf", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require("react");
  return {
    Document: (props: {
      children?: React.ReactNode;
      file?: unknown;
      options?: Record<string, unknown>;
    }) => {
      mockDocumentProps.push({
        file: props.file,
        options: props.options,
      });
      return React.createElement(
        "div",
        { className: "mock-document" },
        props.children,
      );
    },
    Page: () => React.createElement("div", { className: "mock-page" }),
    Thumbnail: () =>
      React.createElement("div", { className: "mock-thumbnail" }),
    pdfjs: {
      GlobalWorkerOptions: {},
    },
  };
});

jest.mock("../PdfControls", () => ({
  PdfControls: () => <div className="mock-controls" />,
}));

jest.mock("../PdfPageViewer", () => ({
  PdfPageViewer: () => <div className="mock-page-viewer" />,
}));

jest.mock("../PdfThumbnailSidebar", () => ({
  PdfThumbnailSidebar: () => <div className="mock-thumbnail-sidebar" />,
}));

jest.mock("../useRedirectDisclaimer", () => ({
  useRedirectDisclaimer: () => ({
    handlePdfClick: jest.fn(),
  }),
}));

describe("PreviewPdf", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    mockDocumentProps.length = 0;
    global.fetch = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("passes a direct URL source to react-pdf without prefetching a Blob", () => {
    const src = "https://example.test/demo.pdf";

    const html = renderToStaticMarkup(<PreviewPdf src={src} />);

    expect(mockDocumentProps).toHaveLength(1);
    expect(mockDocumentProps[0].file).toEqual({ url: src });
    expect(mockDocumentProps[0].options).toMatchObject({
      withCredentials: true,
      isEvalSupported: false,
    });
    expect(global.fetch).not.toHaveBeenCalled();
    expect(html).toContain("mock-page-viewer");
  });

  it("configures the bundled pdf.js worker", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { pdfjs } = require("react-pdf");

    renderToStaticMarkup(<PreviewPdf src="https://example.test/demo.pdf" />);

    expect(pdfjs.GlobalWorkerOptions.workerSrc).toBe("/pdf.worker.mjs");
  });
});
