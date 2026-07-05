import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/router";
import { useTranslation } from "react-i18next";
import {
  removeQuotes,
  useCunninghamTheme,
} from "@/features/ui/cunningham/useCunninghamTheme";

import MyApp, { useAppContext } from "../_app";

jest.mock("next/head", () => ({
  __esModule: true,
  default: ({ children }: { children?: React.ReactNode }) => (
    <div>head-mock{children}</div>
  ),
}));

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/i18n/initI18n", () => ({}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  CunninghamProvider: ({
    children,
    currentLocale,
    theme,
  }: {
    children?: React.ReactNode;
    currentLocale: string;
    theme: string;
  }) => (
    <div>{`cunningham-provider:${currentLocale}:${theme}`}{children}</div>
  ),
  ContextMenuProvider: ({ children }: { children?: React.ReactNode }) => (
    <div>context-menu-provider{children}</div>
  ),
}));

jest.mock("@tanstack/react-query-devtools", () => ({
  ReactQueryDevtools: ({ initialIsOpen }: { initialIsOpen: boolean }) => (
    <div>{`react-query-devtools:${String(initialIsOpen)}`}</div>
  ),
}));

jest.mock("@/features/analytics/AnalyticsProvider", () => ({
  AnalyticsProvider: ({ children }: { children?: React.ReactNode }) => (
    <div>analytics-provider{children}</div>
  ),
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  ConfigProvider: ({ children }: { children?: React.ReactNode }) => (
    <div>config-provider{children}</div>
  ),
}));

jest.mock("@/features/ui/cunningham/useCunninghamTheme", () => ({
  removeQuotes: jest.fn((value: string) => value.replaceAll('"', "")),
  useCunninghamTheme: jest.fn(),
}));

jest.mock("@/features/ui/components/responsive/ResponsiveDivs", () => ({
  ResponsiveDivs: () => <div>responsive-divs</div>,
}));

jest.mock("@/features/feedback/Feedback", () => ({
  FeedbackFooterMobile: () => <div>feedback-footer-mobile</div>,
}));

const mockedUseRouter = jest.mocked(useRouter);
const mockedUseTranslation = jest.mocked(useTranslation);
const mockedUseCunninghamTheme = jest.mocked(useCunninghamTheme);
const mockedRemoveQuotes = jest.mocked(removeQuotes);

const ContextProbePage = () => {
  const { theme } = useAppContext();

  return <div>{`page-theme:${theme}`}</div>;
};

ContextProbePage.getLayout = (page: React.ReactElement) => (
  <div>custom-layout{page}</div>
);

describe("MyApp", () => {
  const originalNodeEnv = process.env.NODE_ENV;

  beforeEach(() => {
    (process.env as Record<string, string | undefined>).NODE_ENV = "test";
    mockedUseRouter.mockReturnValue({
      pathname: "/explorer/items/my-files",
    } as never);
    mockedUseTranslation.mockReturnValue({
      i18n: {
        language: "fr-fr",
      },
      t: (key: string) => `translated:${key}`,
    } as never);
    mockedUseCunninghamTheme.mockReturnValue({
      components: {
        favicon: {
          src: '"/favicon-theme.png"',
        },
      },
    } as never);
    mockedRemoveQuotes.mockClear();
  });

  afterEach(() => {
    (process.env as Record<string, string | undefined>).NODE_ENV =
      originalNodeEnv;
  });

  it("keeps the canonical provider composition and page getLayout wiring", () => {
    const html = renderToStaticMarkup(
      <MyApp
        Component={ContextProbePage as never}
        pageProps={{}}
        router={{} as never}
      />,
    );

    expect(html).toContain("head-mock");
    expect(html).toContain("translated:app_title");
    expect(html).toContain("cunningham-provider:fr-FR:anct");
    expect(html).toContain("config-provider");
    expect(html).toContain("analytics-provider");
    expect(html).toContain("context-menu-provider");
    expect(html).toContain("custom-layout");
    expect(html).toContain("page-theme:anct");
    expect(html).toContain("responsive-divs");
    expect(html).toContain("feedback-footer-mobile");
    expect(mockedRemoveQuotes).toHaveBeenCalledWith('"/favicon-theme.png"');
  });

  it("hides the mobile feedback footer on SDK routes", () => {
    mockedUseRouter.mockReturnValue({
      pathname: "/sdk/explorer",
    } as never);

    const html = renderToStaticMarkup(
      <MyApp
        Component={ContextProbePage as never}
        pageProps={{}}
        router={{} as never}
      />,
    );

    expect(html).not.toContain("feedback-footer-mobile");
  });

  it("shows the devtools only in development mode", () => {
    (process.env as Record<string, string | undefined>).NODE_ENV =
      "development";

    const html = renderToStaticMarkup(
      <MyApp
        Component={ContextProbePage as never}
        pageProps={{}}
        router={{} as never}
      />,
    );

    expect(html).toContain("react-query-devtools:false");
  });

  it("keeps useAppContext guarded outside the app provider", () => {
    const OutsideProbe = () => {
      useAppContext();
      return <div>outside</div>;
    };

    expect(() => renderToStaticMarkup(<OutsideProbe />)).toThrow(
      "useAppContext must be used within an AppContextProvider",
    );
  });
});
