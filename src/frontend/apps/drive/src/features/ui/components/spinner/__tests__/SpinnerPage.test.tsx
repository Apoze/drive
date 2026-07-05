import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SpinnerPage } from "../SpinnerPage";

const renderedSpinners: Array<Record<string, unknown>> = [];

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Spinner: (props: { size?: string }) => {
    renderedSpinners.push(props as Record<string, unknown>);
    return <div>spinner:{props.size}</div>;
  },
}));

describe("SpinnerPage", () => {
  beforeEach(() => {
    renderedSpinners.length = 0;
  });

  it("keeps the spinner wrapper and xl spinner size", () => {
    const html = renderToStaticMarkup(<SpinnerPage />);

    expect(html).toContain("drive__spinner-page");
    expect(html).toContain("spinner:xl");
    expect(renderedSpinners[0]).toMatchObject({ size: "xl" });
  });
});
