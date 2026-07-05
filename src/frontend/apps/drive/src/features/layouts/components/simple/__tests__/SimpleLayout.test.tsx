import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { SimpleLayout, getSimpleLayout } from "../SimpleLayout";

const renderedMainLayouts: Array<Record<string, unknown>> = [];

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  MainLayout: (props: {
    children?: React.ReactNode;
    enableResize?: boolean;
    hideLeftPanelOnDesktop?: boolean;
    leftPanelContent?: React.ReactNode;
    rightHeaderContent?: React.ReactNode;
  }) => {
    renderedMainLayouts.push(props as Record<string, unknown>);
    return (
      <div>
        main-layout
        {props.leftPanelContent}
        {props.rightHeaderContent}
        {props.children}
      </div>
    );
  },
}));

jest.mock("../../global/GlobalLayout", () => ({
  GlobalLayout: ({ children }: { children?: React.ReactNode }) => (
    <div>global-layout{children}</div>
  ),
}));

jest.mock("../../header/Header", () => ({
  HeaderRight: () => <div>header-right</div>,
}));

jest.mock("../../left-panel/LeftPanelMobile", () => ({
  LeftPanelMobile: () => <div>left-panel-mobile</div>,
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  Toaster: () => <div>toaster</div>,
}));

describe("SimpleLayout", () => {
  beforeEach(() => {
    renderedMainLayouts.length = 0;
  });

  it("renders the canonical simple layout wiring", () => {
    const html = renderToStaticMarkup(
      <SimpleLayout>
        <div>simple-page</div>
      </SimpleLayout>,
    );

    expect(html).toContain("global-layout");
    expect(html).toContain("main-layout");
    expect(html).toContain("left-panel-mobile");
    expect(html).toContain("header-right");
    expect(html).toContain("simple-page");
    expect(html).toContain("toaster");
    expect(renderedMainLayouts[0]).toEqual(
      expect.objectContaining({
        enableResize: true,
        hideLeftPanelOnDesktop: true,
      }),
    );
  });

  it("wraps pages through getSimpleLayout", () => {
    const html = renderToStaticMarkup(getSimpleLayout(<div>page-slot</div>));

    expect(html).toContain("page-slot");
    expect(html).toContain("toaster");
  });
});
