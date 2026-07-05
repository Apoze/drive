import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { useConfig } from "@/features/config/ConfigProvider";

import { useThemeCustomization } from "../useThemeCustomization";

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: jest.fn(),
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedUseConfig = jest.mocked(useConfig);

const Probe = () => {
  const footer = useThemeCustomization("footer");
  return <div>{JSON.stringify(footer)}</div>;
};

describe("useThemeCustomization", () => {
  it("returns the merged default and language-specific footer customization", () => {
    mockedUseTranslation.mockReturnValue({
      i18n: {
        language: "fr-fr",
      },
    } as never);
    mockedUseConfig.mockReturnValue({
      config: {
        theme_customization: {
          footer: {
            default: {
              accessibility: "noncompliant",
            },
            fr: {
              contentDescription: "Description FR",
            },
          },
        },
      },
    } as never);

    const html = renderToStaticMarkup(<Probe />);

    expect(html).toContain("noncompliant");
    expect(html).toContain("Description FR");
  });

  it("falls back to the default footer customization when the language is unknown", () => {
    mockedUseTranslation.mockReturnValue({
      i18n: {
        language: "es-es",
      },
    } as never);
    mockedUseConfig.mockReturnValue({
      config: {
        theme_customization: {
          footer: {
            default: {
              contentDescription: "Default description",
            },
          },
        },
      },
    } as never);

    const html = renderToStaticMarkup(<Probe />);

    expect(html).toContain("Default description");
  });
});
