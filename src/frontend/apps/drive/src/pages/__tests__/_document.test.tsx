import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import Document from "../_document";

jest.mock("next/document", () => ({
  Html: ({ children }: { children?: React.ReactNode }) => (
    <html data-doc="html">{children}</html>
  ),
  Head: () => <head data-doc="head" />,
  Main: () => <main data-doc="main" />,
  NextScript: () => <script data-doc="next-script" />,
}));

describe("Document", () => {
  it("keeps the minimal Next document structure", () => {
    const html = renderToStaticMarkup(<Document />);

    expect(html).toContain('data-doc="html"');
    expect(html).toContain('data-doc="head"');
    expect(html).toContain('data-doc="main"');
    expect(html).toContain('data-doc="next-script"');
    expect(html.indexOf('data-doc="head"')).toBeLessThan(
      html.indexOf('data-doc="main"'),
    );
  });
});
