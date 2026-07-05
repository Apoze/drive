import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ResponsiveDivs, isTablet } from "../ResponsiveDivs";

describe("ResponsiveDivs", () => {
  const originalDocument = global.document;
  const originalGetComputedStyle = global.getComputedStyle;

  afterEach(() => {
    if (originalDocument === undefined) {
      Object.defineProperty(global, "document", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "document", {
        configurable: true,
        value: originalDocument,
      });
    }

    if (originalGetComputedStyle === undefined) {
      Object.defineProperty(global, "getComputedStyle", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "getComputedStyle", {
        configurable: true,
        value: originalGetComputedStyle,
      });
    }
  });

  it("renders the shared responsive sentinel", () => {
    const html = renderToStaticMarkup(<ResponsiveDivs />);

    expect(html).toContain('id="responsive-tablet"');
  });

  it("detects tablet mode when the sentinel is displayed as block", () => {
    const sentinel = { id: "responsive-tablet" } as Element;
    const querySelector = jest.fn(() => sentinel);
    const getPropertyValue = jest.fn(() => "block");

    Object.defineProperty(global, "document", {
      configurable: true,
      value: { querySelector },
    });
    Object.defineProperty(global, "getComputedStyle", {
      configurable: true,
      value: jest.fn(() => ({ getPropertyValue })),
    });

    expect(isTablet()).toBe(true);
    expect(querySelector).toHaveBeenCalledWith("#responsive-tablet");
    expect(getPropertyValue).toHaveBeenCalledWith("display");
  });

  it("returns false when the sentinel is not displayed as block", () => {
    Object.defineProperty(global, "document", {
      configurable: true,
      value: {
        querySelector: jest.fn(() => ({ id: "responsive-tablet" })),
      },
    });
    Object.defineProperty(global, "getComputedStyle", {
      configurable: true,
      value: jest.fn(() => ({
        getPropertyValue: jest.fn(() => "none"),
      })),
    });

    expect(isTablet()).toBe(false);
  });
});
