import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { IconSvg } from "../Icon";

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  IconSize: {
    SMALL: "small",
    MEDIUM: "medium",
  },
  iconSizeMap: {
    small: 16,
    medium: 24,
  },
}));

describe("IconSvg", () => {
  it("uses an explicit numeric size when provided", () => {
    const html = renderToStaticMarkup(
      <IconSvg size={32}>
        <path d="M0 0" />
      </IconSvg>,
    );

    expect(html).toContain('width="32"');
    expect(html).toContain('height="32"');
    expect(html).toContain("<path");
  });

  it("uses iconSizeMap for shared IconSize tokens", () => {
    const html = renderToStaticMarkup(<IconSvg size={"small" as never} />);

    expect(html).toContain('width="16"');
    expect(html).toContain('height="16"');
  });

  it("falls back to 24 when no size is provided", () => {
    const html = renderToStaticMarkup(<IconSvg />);

    expect(html).toContain('width="24"');
    expect(html).toContain('height="24"');
  });
});
