import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useConfig } from "@/features/config/ConfigProvider";
import { useAppContext } from "@/pages/_app";
import {
  removeQuotes,
  useCunninghamTheme,
} from "@/features/ui/cunningham/useCunninghamTheme";
import { Gaufre } from "../Gaufre";

const renderedGaufres: Array<Record<string, unknown>> = [];

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  LaGaufreV2: (props: {
    widgetPath: string;
    apiUrl: string;
    showMoreLimit: number;
  }) => {
    renderedGaufres.push(props as Record<string, unknown>);
    return (
      <div>
        gaufre:{props.widgetPath}:{props.apiUrl}:{props.showMoreLimit}
      </div>
    );
  },
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: jest.fn(),
}));

jest.mock("@/pages/_app", () => ({
  useAppContext: jest.fn(),
}));

jest.mock("@/features/ui/cunningham/useCunninghamTheme", () => ({
  useCunninghamTheme: jest.fn(),
  removeQuotes: jest.fn((value: string) => value.replaceAll('"', "")),
}));

const mockedUseConfig = jest.mocked(useConfig);
const mockedUseAppContext = jest.mocked(useAppContext);
const mockedUseCunninghamTheme = jest.mocked(useCunninghamTheme);
const mockedRemoveQuotes = jest.mocked(removeQuotes);

describe("Gaufre", () => {
  beforeEach(() => {
    renderedGaufres.length = 0;
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_HIDE_GAUFRE: false,
      },
    } as never);
    mockedUseAppContext.mockReturnValue({
      theme: "default",
    } as never);
    mockedUseCunninghamTheme.mockReturnValue({
      components: {
        gaufre: {
          widgetPath: '"/widget.js"',
          apiUrl: '"https://api.example.test"',
        },
      },
    } as never);
    mockedRemoveQuotes.mockClear();
  });

  it("hides the gaufre when config disables it", () => {
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_HIDE_GAUFRE: true,
      },
    } as never);

    const html = renderToStaticMarkup(<Gaufre />);

    expect(html).toBe("");
    expect(renderedGaufres).toHaveLength(0);
  });

  it("keeps widgetPath/apiUrl wiring and default showMoreLimit", () => {
    const html = renderToStaticMarkup(<Gaufre />);

    expect(html).toContain("gaufre:/widget.js:https://api.example.test:6");
    expect(mockedRemoveQuotes).toHaveBeenNthCalledWith(1, '"/widget.js"');
    expect(mockedRemoveQuotes).toHaveBeenNthCalledWith(
      2,
      '"https://api.example.test"',
    );
  });

  it("uses the ANCT limit when theme is anct", () => {
    mockedUseAppContext.mockReturnValue({
      theme: "anct",
    } as never);

    const html = renderToStaticMarkup(<Gaufre />);

    expect(html).toContain("gaufre:/widget.js:https://api.example.test:100");
  });
});
