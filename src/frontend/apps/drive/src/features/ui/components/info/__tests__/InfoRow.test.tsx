import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { InfoRow } from "../InfoRow";

describe("InfoRow", () => {
  it("keeps the string right-content class and rendering", () => {
    const html = renderToStaticMarkup(
      <InfoRow label="Owner" rightContent="Jane Doe" />,
    );

    expect(html).toContain("info-row__label");
    expect(html).toContain("Owner");
    expect(html).toContain("info-row__right-content__string");
    expect(html).toContain("Jane Doe");
  });

  it("keeps node right-content rendering without the string class", () => {
    const html = renderToStaticMarkup(
      <InfoRow label="Access" rightContent={<strong>Restricted</strong>} />,
    );

    expect(html).toContain("<strong>Restricted</strong>");
    expect(html).not.toContain("info-row__right-content__string");
  });
});
