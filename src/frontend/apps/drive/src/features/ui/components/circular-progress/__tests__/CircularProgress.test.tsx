import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CircularProgress } from "../CircularProgress";

jest.mock("@/features/ui/components/icon/CheckIcon", () => ({
  CheckIcon: () => <div>check-icon</div>,
}));

describe("CircularProgress", () => {
  it("keeps the progress circle rendering below completion", () => {
    const html = renderToStaticMarkup(<CircularProgress progress={25} />);

    expect(html).toContain("stroke-dashoffset");
    expect(html).toContain("rotate(-90deg)");
    expect(html).not.toContain("check-icon");
  });

  it("clamps progress to 100 and renders the completion check", () => {
    const html = renderToStaticMarkup(<CircularProgress progress={150} />);

    expect(html).toContain("check-icon");
    expect(html).not.toContain("<circle");
  });
});
