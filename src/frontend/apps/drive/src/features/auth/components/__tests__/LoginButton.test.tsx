import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { login } from "../../Auth";
import { LoginButton } from "../LoginButton";

const SESSION_STORAGE_REDIRECT_AFTER_LOGIN_URL = "redirect_after_login_url";

const renderedButtons: Array<Record<string, unknown>> = [];

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    className?: string;
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

jest.mock("@/features/api/fetchApi", () => ({
  SESSION_STORAGE_REDIRECT_AFTER_LOGIN_URL: "redirect_after_login_url",
}));

jest.mock("../../Auth", () => ({
  login: jest.fn(),
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedLogin = jest.mocked(login);

describe("LoginButton", () => {
  const originalWindow = global.window;
  const setItem = jest.fn();

  beforeEach(() => {
    renderedButtons.length = 0;
    setItem.mockClear();
    mockedLogin.mockClear();
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);

    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          href: "http://192.168.10.123:3000/explorer/items/files",
        },
      },
    });
    Object.defineProperty(global, "sessionStorage", {
      configurable: true,
      value: {
        setItem,
      },
    });
  });

  afterEach(() => {
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

  it("stores the current URL before delegating to login", () => {
    const html = renderToStaticMarkup(<LoginButton />);

    expect(html).toContain("translated:login");
    expect(renderedButtons[0]).toEqual(
      expect.objectContaining({
        className: "drive__header__login-button",
        variant: "tertiary",
      }),
    );

    (renderedButtons[0].onClick as () => void)();

    expect(setItem).toHaveBeenCalledWith(
      SESSION_STORAGE_REDIRECT_AFTER_LOGIN_URL,
      "http://192.168.10.123:3000/explorer/items/files",
    );
    expect(mockedLogin).toHaveBeenCalledTimes(1);
  });
});
