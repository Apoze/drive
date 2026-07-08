import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { login } from "@/features/auth/Auth";
import UnauthorizedPage from "@/pages/401";

const renderedButtons: Array<Record<string, unknown>> = [];
const renderedDisclaimers: Array<Record<string, unknown>> = [];

jest.mock("@/features/auth/Auth", () => ({
  login: jest.fn(),
}));

jest.mock("@/features/layouts/components/simple/SimpleLayout", () => ({
  getSimpleLayout: (page: React.ReactElement) => <div>simple-layout{page}</div>,
}));

jest.mock("@/features/ui/components/generic-disclaimer/GenericDisclaimer", () => ({
  GenericDisclaimer: (props: {
    children?: React.ReactNode;
    imageSrc: string;
    message: string;
  }) => {
    renderedDisclaimers.push(props as Record<string, unknown>);
    return (
      <div>
        disclaimer:{props.message}:{props.imageSrc}
        {props.children}
      </div>
    );
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => {
    renderedButtons.push(props as Record<string, unknown>);
    return <button>{props.children}</button>;
  },
}));

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedLogin = jest.mocked(login);

describe("401 page", () => {
  const originalWindow = global.window;

  beforeEach(() => {
    renderedButtons.length = 0;
    renderedDisclaimers.length = 0;
    mockedLogin.mockClear();
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          origin: "http://192.168.10.123:3000",
        },
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

  it("renders the disclaimer and redirects login to home", () => {
    const html = renderToStaticMarkup(<UnauthorizedPage />);

    expect(html).toContain(
      "disclaimer:translated:401.title:/assets/401-background.png",
    );
    expect(html).toContain("translated:401.button");
    expect(renderedDisclaimers).toHaveLength(1);

    (renderedButtons[0].onClick as () => void)();

    expect(mockedLogin).toHaveBeenCalledWith("http://192.168.10.123:3000/");
  });
});
