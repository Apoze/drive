import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { SdkLayout, SdkPickerLayout, getSdkLayout } from "../SdkLayout";

const renderedProviders: Array<Record<string, unknown>> = [];

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  Auth: ({ children }: { children?: React.ReactNode }) => <div>auth{children}</div>,
}));

jest.mock("@/features/explorer/components/GlobalExplorerContext", () => ({
  GlobalExplorerProvider: (props: Record<string, unknown>) => {
    renderedProviders.push(props);
    return <div>global-explorer{props.children as React.ReactNode}</div>;
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  HorizontalSeparator: () => <div>separator</div>,
  Spinner: ({ size }: { size: string }) => <div>spinner:{size}</div>,
}));

const mockedUseTranslation = jest.mocked(useTranslation);

describe("SdkLayout", () => {
  beforeEach(() => {
    renderedProviders.length = 0;
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
  });

  it("wraps the SDK page with Auth and GlobalExplorerProvider", () => {
    const html = renderToStaticMarkup(
      <SdkLayout>
        <div>sdk-content</div>
      </SdkLayout>,
    );

    expect(html).toContain("auth");
    expect(html).toContain("global-explorer");
    expect(html).toContain("translated:sdk.explorer.picker_caption");
    expect(html).toContain("separator");
    expect(renderedProviders[0]).toEqual(
      expect.objectContaining({
        displayMode: "sdk",
        itemId: "",
        onNavigate: expect.any(Function),
      }),
    );
  });

  it("wraps pages through getSdkLayout", () => {
    const html = renderToStaticMarkup(getSdkLayout(<div>sdk-page</div>));

    expect(html).toContain("sdk-page");
  });

  it("shows a spinner while the sdk token is not loaded", () => {
    const html = renderToStaticMarkup(
      <SdkPickerLayout>
        <div>picker-content</div>
      </SdkPickerLayout>,
    );

    expect(html).toContain("spinner:xl");
    expect(html).not.toContain("picker-content");
  });

  it("renders the picker content once the token is available", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy.mockReturnValueOnce(["sdk-token", jest.fn()] as never);

    const html = renderToStaticMarkup(
      <SdkPickerLayout>
        <div>picker-content</div>
      </SdkPickerLayout>,
    );

    expect(html).toContain("picker-content");
    expect(html).not.toContain("spinner:xl");

    useStateSpy.mockRestore();
  });
});
