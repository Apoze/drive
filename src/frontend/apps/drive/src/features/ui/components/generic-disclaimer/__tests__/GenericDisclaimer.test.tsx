import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { GenericDisclaimer } from "../GenericDisclaimer";

describe("GenericDisclaimer", () => {
  it("keeps the image and message rendering intact", () => {
    const html = renderToStaticMarkup(
      <GenericDisclaimer
        message="Preview unavailable"
        imageSrc="/images/unavailable.svg"
      />,
    );

    expect(html).toContain("drive__generic-disclaimer");
    expect(html).toContain('src="/images/unavailable.svg"');
    expect(html).toContain("<p>Preview unavailable</p>");
  });

  it("keeps children rendering under the shared disclaimer shell", () => {
    const html = renderToStaticMarkup(
      <GenericDisclaimer message="Notice" imageSrc="/images/info.svg">
        <button>Retry</button>
      </GenericDisclaimer>,
    );

    expect(html).toContain("Retry");
  });
});
