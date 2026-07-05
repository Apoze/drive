import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { addToast } from "@/features/ui/components/toaster/Toaster";

import { useClipboard, writeTextToClipboard } from "../useCopyToClipboard";

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({
    children,
    type,
  }: {
    children?: React.ReactNode;
    type?: string;
  }) => <div data-type={type}>{children}</div>,
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedAddToast = jest.mocked(addToast);

describe("useCopyToClipboard", () => {
  const originalNavigator = global.navigator;
  const originalDocument = global.document;
  const originalHTMLElement = global.HTMLElement;

  beforeEach(() => {
    mockedAddToast.mockReset();
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
  });

  afterEach(() => {
    if (originalNavigator === undefined) {
      Object.defineProperty(global, "navigator", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "navigator", {
        configurable: true,
        value: originalNavigator,
      });
    }

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

    if (originalHTMLElement === undefined) {
      Object.defineProperty(global, "HTMLElement", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "HTMLElement", {
        configurable: true,
        value: originalHTMLElement,
      });
    }
  });

  it("prefers navigator.clipboard.writeText when available", async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    Object.defineProperty(global, "navigator", {
      configurable: true,
      value: {
        clipboard: { writeText },
      },
    });

    await writeTextToClipboard("copy-me");

    expect(writeText).toHaveBeenCalledWith("copy-me");
  });

  it("falls back to execCommand copy when navigator.clipboard is unavailable", async () => {
    class FakeElement {
      focus = jest.fn();
      select = jest.fn();
      setAttribute = jest.fn();
      setSelectionRange = jest.fn();
      style: Record<string, string> = {};
      value = "";
    }

    const activeElement = new FakeElement();
    const textarea = new FakeElement();
    const appendChild = jest.fn();
    const removeChild = jest.fn();
    const execCommand = jest.fn(() => true);

    Object.defineProperty(global, "HTMLElement", {
      configurable: true,
      value: FakeElement,
    });
    Object.defineProperty(global, "navigator", {
      configurable: true,
      value: {},
    });
    Object.defineProperty(global, "document", {
      configurable: true,
      value: {
        activeElement,
        body: {
          appendChild,
          removeChild,
        },
        createElement: jest.fn(() => textarea),
        execCommand,
      },
    });

    await writeTextToClipboard("fallback-copy");

    expect(appendChild).toHaveBeenCalledWith(textarea);
    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(removeChild).toHaveBeenCalledWith(textarea);
    expect(activeElement.focus).toHaveBeenCalledTimes(1);
  });

  it("shows the success toast after a successful copy", async () => {
    let copy: ((text: string, successMessage?: string, errorMessage?: string) => void) | undefined;
    const writeText = jest.fn().mockResolvedValue(undefined);
    Object.defineProperty(global, "navigator", {
      configurable: true,
      value: {
        clipboard: { writeText },
      },
    });

    const Probe = () => {
      copy = useClipboard();
      return <div>probe</div>;
    };

    renderToStaticMarkup(<Probe />);
    copy?.("share-link", "Copied", "Failed");
    await Promise.resolve();
    await Promise.resolve();

    expect(writeText).toHaveBeenCalledWith("share-link");
    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement),
    ).toContain("Copied");
    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement),
    ).toContain("check");
  });

  it("shows the error toast when both clipboard paths fail", async () => {
    const execCommand = jest.fn(() => false);
    let copy: ((text: string, successMessage?: string, errorMessage?: string) => void) | undefined;

    class FakeElement {
      focus = jest.fn();
      select = jest.fn();
      setAttribute = jest.fn();
      setSelectionRange = jest.fn();
      style: Record<string, string> = {};
      value = "";
    }

    Object.defineProperty(global, "HTMLElement", {
      configurable: true,
      value: FakeElement,
    });
    Object.defineProperty(global, "navigator", {
      configurable: true,
      value: {},
    });
    Object.defineProperty(global, "document", {
      configurable: true,
      value: {
        activeElement: null,
        body: {
          appendChild: jest.fn(),
          removeChild: jest.fn(),
        },
        createElement: jest.fn(() => new FakeElement()),
        execCommand,
      },
    });

    const Probe = () => {
      copy = useClipboard();
      return <div>probe</div>;
    };

    renderToStaticMarkup(<Probe />);
    copy?.("share-link", undefined, "Copy failed");
    await Promise.resolve();
    await Promise.resolve();

    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement),
    ).toContain("Copy failed");
    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement),
    ).toContain("error");
  });
});
