import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "next-i18next";

import { login, useAuth } from "@/features/auth/Auth";
import { useConfig } from "@/features/config/ConfigProvider";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import { useThemeCustomization } from "@/hooks/useThemeCustomization";
import { useRedirectAfterLogin } from "@/hooks/useRedirectAfterLogin";

import HomePage from "@/pages/index";

const renderedButtons: Array<Record<string, unknown>> = [];
const renderedHeroes: Array<Record<string, unknown>> = [];
const renderedFooters: Array<Record<string, unknown>> = [];

jest.mock("next/head", () => ({
  __esModule: true,
  default: ({ children }: { children?: React.ReactNode }) => (
    <div>head-mock{children}</div>
  ),
}));

jest.mock("next-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  login: jest.fn(),
  useAuth: jest.fn(),
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: jest.fn(),
}));

jest.mock("@/features/layouts/components/global/GlobalLayout", () => ({
  GlobalLayout: ({ children }: { children?: React.ReactNode }) => (
    <div>global-layout{children}</div>
  ),
}));

jest.mock("@/features/layouts/components/header/Header", () => ({
  HeaderRight: () => <div>header-right</div>,
}));

jest.mock("@/features/layouts/components/left-panel/LeftPanelMobile", () => ({
  LeftPanelMobile: () => <div>left-panel-mobile</div>,
}));

jest.mock("@/features/feedback/Feedback", () => ({
  Feedback: () => <div>feedback</div>,
}));

jest.mock("@/hooks/useThemeCustomization", () => ({
  useThemeCustomization: jest.fn(),
}));

jest.mock("@/hooks/useRedirectAfterLogin", () => ({
  useRedirectAfterLogin: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  Toaster: () => <div>toaster</div>,
  ToasterItem: ({
    children,
    type,
  }: {
    children?: React.ReactNode;
    type?: string;
  }) => <div data-type={type}>{children}</div>,
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    fullWidth?: boolean;
    href?: string;
    onClick?: () => void;
    target?: string;
    variant?: string;
  }) => {
    renderedButtons.push(props as Record<string, unknown>);
    return <button>{props.children}</button>;
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Hero: (props: Record<string, unknown>) => {
    renderedHeroes.push(props);
    return <div>hero{props.mainButton as React.ReactNode}</div>;
  },
  Footer: (props: Record<string, unknown>) => {
    renderedFooters.push(props);
    return <div>footer</div>;
  },
  HomeGutter: ({ children }: { children?: React.ReactNode }) => (
    <div>home-gutter{children}</div>
  ),
  MainLayout: ({ children }: { children?: React.ReactNode }) => (
    <div>main-layout{children}</div>
  ),
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedUseAuth = jest.mocked(useAuth);
const mockedLogin = jest.mocked(login);
const mockedUseConfig = jest.mocked(useConfig);
const mockedAddToast = jest.mocked(addToast);
const mockedUseThemeCustomization = jest.mocked(useThemeCustomization);
const mockedUseRedirectAfterLogin = jest.mocked(useRedirectAfterLogin);

describe("HomePage", () => {
  const originalWindow = global.window;
  const originalFetch = global.fetch;

  beforeEach(() => {
    renderedButtons.length = 0;
    renderedHeroes.length = 0;
    renderedFooters.length = 0;
    mockedLogin.mockClear();
    mockedAddToast.mockClear();
    mockedUseRedirectAfterLogin.mockClear();
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
    mockedUseAuth.mockReturnValue({
      user: null,
    } as never);
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_MORE_LINK: "https://docs.example.test/more",
      },
    } as never);
    mockedUseThemeCustomization.mockReturnValue({
      contentDescription: "Footer customization",
    } as never);
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          replace: jest.fn(),
          search: "",
        },
      },
    });
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
      } as Response),
    ) as typeof global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
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

  it("hides the home surface when a user already exists", () => {
    mockedUseAuth.mockReturnValue({
      user: { id: "user-1" },
    } as never);

    expect(renderToStaticMarkup(<HomePage />)).toBe("");
    expect(mockedUseRedirectAfterLogin).toHaveBeenCalledTimes(1);
  });

  it("shows the expected auth-error toast for alpha access failures", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          replace: jest.fn(),
          search: "?auth_error=alpha",
        },
      },
    });

    renderToStaticMarkup(<HomePage />);

    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement),
    ).toContain("translated:authentication.error.alpha");
    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement),
    ).toContain("science");

    useEffectSpy.mockRestore();
  });

  it("shows the access-denied auth-error toast when the app rejects the user", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          replace: jest.fn(),
          search: "?auth_error=user_cannot_access_app",
        },
      },
    });

    renderToStaticMarkup(<HomePage />);

    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement),
    ).toContain("translated:authentication.error.user_cannot_access_app");
    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement),
    ).toContain("lock");

    useEffectSpy.mockRestore();
  });

  it("tries the external home redirect before hiding the local home page", async () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_EXTERNAL_HOME_URL: "https://home.example.test",
        FRONTEND_MORE_LINK: "https://docs.example.test/more",
      },
    } as never);

    const html = renderToStaticMarkup(<HomePage />);
    await Promise.resolve();

    expect(html).toBe("");
    expect(global.fetch).toHaveBeenCalledWith("https://home.example.test", {
      method: "HEAD",
      mode: "no-cors",
    });
    expect(global.window.location.replace).toHaveBeenCalledWith(
      "https://home.example.test",
    );

    useEffectSpy.mockRestore();
  });

  it("switches back to the local home page when the external redirect already failed", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_EXTERNAL_HOME_URL: "https://home.example.test",
        FRONTEND_MORE_LINK: "https://docs.example.test/more",
      },
    } as never);
    useStateSpy.mockReturnValueOnce([true, jest.fn()] as never);

    const html = renderToStaticMarkup(<HomePage />);

    expect(html).toContain("hero");
    expect(renderedFooters).toEqual([
      expect.objectContaining({
        contentDescription: "Footer customization",
      }),
    ]);

    useStateSpy.mockRestore();
  });

  it("marks the redirect as failed when the external site is unreachable", async () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    const useStateSpy = jest.spyOn(React, "useState");
    const setRedirectFailed = jest.fn();
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    global.fetch = jest.fn(() => Promise.reject(new Error("offline"))) as never;
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_EXTERNAL_HOME_URL: "https://home.example.test",
        FRONTEND_MORE_LINK: "https://docs.example.test/more",
      },
    } as never);
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    useStateSpy.mockReturnValueOnce([false, setRedirectFailed] as never);

    renderToStaticMarkup(<HomePage />);
    await Promise.resolve();

    expect(setRedirectFailed).toHaveBeenCalledWith(true);
    expect(global.window.location.replace).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();

    warnSpy.mockRestore();
    useStateSpy.mockRestore();
    useEffectSpy.mockRestore();
  });

  it("renders the login and more CTAs on the local home page", () => {
    const html = renderToStaticMarkup(<HomePage />);

    expect(html).toContain("hero");
    expect(html).toContain("footer");
    expect(renderedHeroes[0]).toEqual(
      expect.objectContaining({
        subtitle: "translated:home.subtitle",
        title: "translated:home.title",
      }),
    );

    (renderedButtons[0].onClick as () => void)();

    expect(mockedLogin).toHaveBeenCalledTimes(1);
    expect(renderedButtons[1]).toEqual(
      expect.objectContaining({
        href: "https://docs.example.test/more",
        target: "_blank",
        variant: "bordered",
      }),
    );
  });

  it("keeps the shared global getLayout contract", () => {
    const html = renderToStaticMarkup(HomePage.getLayout(<div>page-slot</div>));

    expect(html).toContain("drive__home");
    expect(html).toContain("drive__home--feedback");
    expect(html).toContain("global-layout");
    expect(html).toContain("page-slot");
  });
});
