import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { useAuth } from "@/features/auth/Auth";

import { useRedirectAfterLogin } from "../useRedirectAfterLogin";

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/features/api/fetchApi", () => ({
  SESSION_STORAGE_REDIRECT_AFTER_LOGIN_URL: "redirect_after_login_url",
}));

const mockedUseAuth = jest.mocked(useAuth);

const Probe = () => {
  useRedirectAfterLogin();
  return <div>probe</div>;
};

describe("useRedirectAfterLogin", () => {
  const originalWindow = global.window;
  const getItem = jest.fn();
  const removeItem = jest.fn();

  beforeEach(() => {
    getItem.mockReset();
    removeItem.mockReset();

    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          href: "http://192.168.10.123:3000/",
        },
      },
    });
    Object.defineProperty(global, "sessionStorage", {
      configurable: true,
      value: {
        getItem,
        removeItem,
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

  it("redirects authenticated users to their attempted URL and clears it", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    getItem.mockReturnValue("http://192.168.10.123:3000/share/token");
    mockedUseAuth.mockReturnValue({
      user: { id: "user-1" },
    } as never);

    renderToStaticMarkup(<Probe />);

    expect(removeItem).toHaveBeenCalledWith("redirect_after_login_url");
    expect(global.window.location.href).toBe(
      "http://192.168.10.123:3000/share/token",
    );

    useEffectSpy.mockRestore();
  });

  it("falls back to my-files when there is no attempted URL", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    getItem.mockReturnValue(null);
    mockedUseAuth.mockReturnValue({
      user: { id: "user-1" },
    } as never);

    renderToStaticMarkup(<Probe />);

    expect(removeItem).not.toHaveBeenCalled();
    expect(global.window.location.href).toBe("/explorer/items/my-files");

    useEffectSpy.mockRestore();
  });

  it("does nothing while the user is anonymous", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    mockedUseAuth.mockReturnValue({
      user: null,
    } as never);

    renderToStaticMarkup(<Probe />);

    expect(getItem).not.toHaveBeenCalled();
    expect(removeItem).not.toHaveBeenCalled();
    expect(global.window.location.href).toBe("http://192.168.10.123:3000/");

    useEffectSpy.mockRestore();
  });
});
