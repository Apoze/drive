import { resolveLocalizedThemeCustomization } from "../themeCustomizationRuntime";

describe("themeCustomizationRuntime", () => {
  it("merges the default customization with the current language override", () => {
    expect(
      resolveLocalizedThemeCustomization(
        {
          default: {
            accessibility: "noncompliant",
            bottomLinks: [{ href: "/mentions", label: "Mentions" }],
          },
          fr: {
            contentDescription: "Description FR",
          },
        },
        "fr-fr",
      ),
    ).toEqual({
      accessibility: "noncompliant",
      bottomLinks: [{ href: "/mentions", label: "Mentions" }],
      contentDescription: "Description FR",
    });
  });

  it("falls back to the default customization when the language is missing", () => {
    expect(
      resolveLocalizedThemeCustomization(
        {
          default: {
            contentDescription: "Default description",
          },
        },
        "es-es",
      ),
    ).toEqual({
      contentDescription: "Default description",
    });
  });
});
