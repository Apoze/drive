import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useSearchParams } from "next/navigation";

import { login, useAuth } from "@/features/auth/Auth";

import SDKPage from "../index";

jest.mock("next/navigation", () => ({
  useSearchParams: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  login: jest.fn(),
  useAuth: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Spinner: ({ size }: { size: string }) => <div>spinner:{size}</div>,
}));

jest.mock("@/features/layouts/components/global/GlobalLayout", () => ({
  GlobalLayout: ({ children }: { children?: React.ReactNode }) => (
    <div>global-layout{children}</div>
  ),
}));

const mockedUseSearchParams = jest.mocked(useSearchParams);
const mockedUseAuth = jest.mocked(useAuth);
const mockedLogin = jest.mocked(login);

describe("SDKPage", () => {
  const originalWindow = global.window;
  const setItem = jest.fn();

  beforeEach(() => {
    setItem.mockClear();
    mockedLogin.mockClear();
    mockedUseSearchParams.mockReturnValue({
      get: (key: string) =>
        key === "token" ? "sdk-token" : key === "mode" ? "save" : null,
    } as never);
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          href: "http://192.168.10.123:3000/sdk?token=sdk-token&mode=save",
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

  it("renders the SDK loading spinner", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
    } as never);

    const html = renderToStaticMarkup(<SDKPage />);

    expect(html).toContain("spinner:xl");
  });

  it("throws when the SDK token is missing", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    mockedUseAuth.mockReturnValue({
      user: null,
    } as never);
    mockedUseSearchParams.mockReturnValue({
      get: () => null,
    } as never);
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });

    expect(() => renderToStaticMarkup(<SDKPage />)).toThrow("Token is required");

    useEffectSpy.mockRestore();
  });

  it("stores the SDK token and redirects authenticated users", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    mockedUseAuth.mockReturnValue({
      user: { id: "user-1" },
    } as never);
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });

    renderToStaticMarkup(<SDKPage />);

    expect(setItem).toHaveBeenCalledWith("sdk_token", "sdk-token");
    expect(global.window.location.href).toBe("/sdk/explorer?mode=save");
    expect(mockedLogin).not.toHaveBeenCalled();

    useEffectSpy.mockRestore();
  });

  it("stores the SDK token and asks anonymous users to login", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    mockedUseAuth.mockReturnValue({
      user: null,
    } as never);
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });

    renderToStaticMarkup(<SDKPage />);

    expect(setItem).toHaveBeenCalledWith("sdk_token", "sdk-token");
    expect(mockedLogin).toHaveBeenCalledWith(
      "http://192.168.10.123:3000/sdk?token=sdk-token&mode=save",
    );

    useEffectSpy.mockRestore();
  });
});
