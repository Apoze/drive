import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { useConfig } from "@/features/config/ConfigProvider";

import { AnalyticsProvider } from "../AnalyticsProvider";

const renderedProviders: Array<Record<string, unknown>> = [];

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: jest.fn(),
}));

jest.mock("posthog-js/react", () => ({
  PostHogProvider: (props: {
    apiKey: string;
    children?: React.ReactNode;
    options?: Record<string, unknown>;
  }) => {
    renderedProviders.push(props as Record<string, unknown>);
    return <div>posthog-provider{props.children}</div>;
  },
}));

const mockedUseConfig = jest.mocked(useConfig);

describe("AnalyticsProvider", () => {
  beforeEach(() => {
    renderedProviders.length = 0;
  });

  it("returns children unchanged when POSTHOG is disabled", () => {
    mockedUseConfig.mockReturnValue({
      config: {},
    } as never);

    const html = renderToStaticMarkup(
      <AnalyticsProvider>
        <div>analytics-children</div>
      </AnalyticsProvider>,
    );

    expect(html).toContain("analytics-children");
    expect(html).not.toContain("posthog-provider");
    expect(renderedProviders).toHaveLength(0);
  });

  it("delegates to PostHogProvider when a key is configured", () => {
    mockedUseConfig.mockReturnValue({
      config: {
        POSTHOG_HOST: "https://posthog.example.test",
        POSTHOG_KEY: "ph-key",
      },
    } as never);

    const html = renderToStaticMarkup(
      <AnalyticsProvider>
        <div>analytics-children</div>
      </AnalyticsProvider>,
    );

    expect(html).toContain("posthog-provider");
    expect(renderedProviders[0]).toEqual(
      expect.objectContaining({
        apiKey: "ph-key",
        options: expect.objectContaining({
          api_host: "https://posthog.example.test",
        }),
      }),
    );
  });
});
