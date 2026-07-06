import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import UnauthorizedPage from "@/pages/403";

const renderedButtons: Array<Record<string, unknown>> = [];
const renderedDisclaimers: Array<Record<string, unknown>> = [];

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

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: ({ name }: { name: string }) => <div>icon:{name}</div>,
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    href?: string;
    icon?: React.ReactNode;
  }) => {
    renderedButtons.push(props as Record<string, unknown>);
    return (
      <button>
        {props.icon}
        {props.children}
      </button>
    );
  },
}));

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

const mockedUseTranslation = jest.mocked(useTranslation);

describe("403 page", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
    renderedDisclaimers.length = 0;
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
  });

  it("renders the disclaimer and the home button", () => {
    const html = renderToStaticMarkup(<UnauthorizedPage />);

    expect(html).toContain(
      "disclaimer:translated:403.title:/assets/403-background.png",
    );
    expect(html).toContain("translated:403.button");
    expect(html).toContain("icon:home");
    expect(renderedDisclaimers).toHaveLength(1);
    expect(renderedButtons[0]).toEqual(
      expect.objectContaining({
        href: "/",
      }),
    );
  });
});
