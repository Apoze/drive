import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/features/auth/Auth";
import { useConfig } from "@/features/config/ConfigProvider";

import { useMessagesWidget } from "../useMessagesWidget";

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: jest.fn(),
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedUseAuth = jest.mocked(useAuth);
const mockedUseConfig = jest.mocked(useConfig);

let capturedShowWidget: (() => void) | null = null;

const Probe = () => {
  capturedShowWidget = useMessagesWidget().showWidget;
  return <div>probe</div>;
};

describe("useMessagesWidget", () => {
  const originalDocument = global.document;
  const originalWindow = global.window;

  beforeEach(() => {
    capturedShowWidget = null;
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
    mockedUseAuth.mockReturnValue({
      user: {
        email: "jane@example.test",
      },
    } as never);
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_FEEDBACK_MESSAGES_WIDGET_API_URL:
          "https://api.example.test",
        FRONTEND_FEEDBACK_MESSAGES_WIDGET_CHANNEL: "support",
        FRONTEND_FEEDBACK_MESSAGES_WIDGET_PATH: "https://cdn.example.test/",
      },
    } as never);
  });

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
    if (originalWindow === undefined) {
      Object.defineProperty(global, "window", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "window", {
        configurable: true,
        value: originalWindow,
      });
    }
  });

  it("throws when required widget config is missing", () => {
    mockedUseConfig.mockReturnValue({
      config: {},
    } as never);

    renderToStaticMarkup(<Probe />);

    expect(() => capturedShowWidget?.()).toThrow(
      "FRONTEND_FEEDBACK_MESSAGES_WIDGET_API_URL, FRONTEND_FEEDBACK_MESSAGES_WIDGET_PATH or FRONTEND_FEEDBACK_MESSAGES_WIDGET_CHANNEL is not set",
    );
  });

  it("pushes widget config and injects the script only once", () => {
    const push = jest.fn();
    const insertBefore = jest.fn();
    const createdScript = {} as HTMLScriptElement;
    const querySelector = jest
      .fn()
      .mockReturnValueOnce(null)
      .mockReturnValueOnce({});

    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        _stmsg_widget: {
          push,
        },
      },
    });
    Object.defineProperty(global, "document", {
      configurable: true,
      value: {
        createElement: jest.fn(() => createdScript),
        getElementsByTagName: jest.fn(() => [
          {
            parentNode: {
              insertBefore,
            },
          },
        ]),
        querySelector,
      },
    });

    renderToStaticMarkup(<Probe />);

    capturedShowWidget?.();
    capturedShowWidget?.();

    expect(push).toHaveBeenCalledTimes(2);
    expect(push).toHaveBeenNthCalledWith(1, [
      "feedback",
      "init",
      expect.objectContaining({
        api: "https://api.example.test",
        channel: "support",
        email: "jane@example.test",
        title: "translated:feedback_widget.title",
      }),
    ]);
    expect(insertBefore).toHaveBeenCalledTimes(1);
  });
});
