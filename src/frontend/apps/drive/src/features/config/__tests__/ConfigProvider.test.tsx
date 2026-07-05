import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { useAppContext } from "@/pages/_app";

import { setRuntimeConfig } from "../runtimeConfig";
import { useApiConfig } from "../useApiConfig";
import { ConfigProvider } from "../ConfigProvider";

const renderedButtons: Array<Record<string, unknown>> = [];
const renderedSpinners: Array<Record<string, unknown>> = [];
const renderedScripts: Array<Record<string, unknown>> = [];

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Spinner: (props: { size?: string }) => {
    renderedSpinners.push(props as Record<string, unknown>);
    return <div>spinner:{props.size}</div>;
  },
}));

jest.mock("next/head", () => ({
  __esModule: true,
  default: ({ children }: { children?: React.ReactNode }) => (
    <div>head-mock{children}</div>
  ),
}));

jest.mock("next/script", () => ({
  __esModule: true,
  default: (props: { src: string }) => {
    renderedScripts.push(props as Record<string, unknown>);
    return <div>script:{props.src}</div>;
  },
}));

jest.mock("../useApiConfig", () => ({
  useApiConfig: jest.fn(),
}));

jest.mock("@/pages/_app", () => ({
  useAppContext: jest.fn(),
}));

jest.mock("../runtimeConfig", () => ({
  setRuntimeConfig: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    onClick?: () => void;
    variant?: string;
  }) => {
    renderedButtons.push(props as Record<string, unknown>);
    return <button>{props.children}</button>;
  },
}));

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/operations/timeBounds", () => ({
  getOperationTimeBound: jest.fn(() => ({
    failed_ms: 5000,
    still_working_ms: 2000,
  })),
}));

jest.mock("@/features/operations/useTimeBoundedPhase", () => ({
  useTimeBoundedPhase: jest.fn(),
}));

const mockedUseApiConfig = jest.mocked(useApiConfig);
const mockedUseAppContext = jest.mocked(useAppContext);
const mockedSetRuntimeConfig = jest.mocked(setRuntimeConfig);
const mockedUseTranslation = jest.mocked(useTranslation);

describe("ConfigProvider", () => {
  const setTheme = jest.fn();

  beforeEach(() => {
    renderedButtons.length = 0;
    renderedSpinners.length = 0;
    renderedScripts.length = 0;
    setTheme.mockClear();
    mockedSetRuntimeConfig.mockClear();
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
    mockedUseAppContext.mockReturnValue({
      setTheme,
    } as never);
  });

  it("renders the loading branch with the shared spinner", () => {
    const { useTimeBoundedPhase } = jest.requireMock(
      "@/features/operations/useTimeBoundedPhase",
    ) as { useTimeBoundedPhase: jest.Mock };
    useTimeBoundedPhase.mockReturnValue("loading");
    mockedUseApiConfig.mockReturnValue({
      data: undefined,
      isError: false,
      isLoading: true,
      refetch: jest.fn(),
    } as never);

    const html = renderToStaticMarkup(
      <ConfigProvider>
        <div>config-children</div>
      </ConfigProvider>,
    );

    expect(html).toContain("spinner:xl");
    expect(html).not.toContain("translated:operations.long_running.still_working");
    expect(renderedSpinners).toHaveLength(1);
  });

  it("renders the still-working branch when config loading takes longer", () => {
    const { useTimeBoundedPhase } = jest.requireMock(
      "@/features/operations/useTimeBoundedPhase",
    ) as { useTimeBoundedPhase: jest.Mock };
    useTimeBoundedPhase.mockReturnValue("still_working");
    mockedUseApiConfig.mockReturnValue({
      data: undefined,
      isError: false,
      isLoading: true,
      refetch: jest.fn(),
    } as never);

    const html = renderToStaticMarkup(
      <ConfigProvider>
        <div>config-children</div>
      </ConfigProvider>,
    );

    expect(html).toContain("translated:operations.long_running.still_working");
  });

  it("renders retry controls when config loading failed", () => {
    const refetch = jest.fn();
    const { useTimeBoundedPhase } = jest.requireMock(
      "@/features/operations/useTimeBoundedPhase",
    ) as { useTimeBoundedPhase: jest.Mock };
    useTimeBoundedPhase.mockReturnValue("failed");
    mockedUseApiConfig.mockReturnValue({
      data: undefined,
      isError: false,
      isLoading: false,
      refetch,
    } as never);

    const html = renderToStaticMarkup(
      <ConfigProvider>
        <div>config-children</div>
      </ConfigProvider>,
    );

    expect(html).toContain("translated:operations.long_running.failed");
    expect(html).toContain("translated:common.retry");

    (renderedButtons[0].onClick as () => void)();
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the explicit error branch with retry controls", () => {
    const refetch = jest.fn();
    const { useTimeBoundedPhase } = jest.requireMock(
      "@/features/operations/useTimeBoundedPhase",
    ) as { useTimeBoundedPhase: jest.Mock };
    useTimeBoundedPhase.mockReturnValue("loading");
    mockedUseApiConfig.mockReturnValue({
      data: undefined,
      isError: true,
      isLoading: false,
      refetch,
    } as never);

    const html = renderToStaticMarkup(
      <ConfigProvider>
        <div>config-children</div>
      </ConfigProvider>,
    );

    expect(html).toContain("translated:operations.long_running.failed");
    expect(html).toContain("translated:common.retry");
  });

  it("renders children on success and applies theme/runtime config/assets", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });

    const config = {
      FRONTEND_CSS_URL: "https://cdn.example.test/theme.css",
      FRONTEND_JS_URL: "https://cdn.example.test/theme.js",
      FRONTEND_THEME: "anct",
      POSTHOG_KEY: "ph-key",
    };
    const { useTimeBoundedPhase } = jest.requireMock(
      "@/features/operations/useTimeBoundedPhase",
    ) as { useTimeBoundedPhase: jest.Mock };
    useTimeBoundedPhase.mockReturnValue("loading");
    mockedUseApiConfig.mockReturnValue({
      data: config,
      isError: false,
      isLoading: false,
      refetch: jest.fn(),
    } as never);

    const html = renderToStaticMarkup(
      <ConfigProvider>
        <div>config-children</div>
      </ConfigProvider>,
    );

    expect(html).toContain("config-children");
    expect(html).toContain("head-mock");
    expect(html).toContain("theme.css");
    expect(html).toContain("script:https://cdn.example.test/theme.js");
    expect(setTheme).toHaveBeenCalledWith("anct");
    expect(mockedSetRuntimeConfig).toHaveBeenCalledWith(config);
    expect(renderedScripts).toHaveLength(1);

    useEffectSpy.mockRestore();
  });
});
