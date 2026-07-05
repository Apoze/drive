import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { logout } from "../../Auth";
import { LogoutButton } from "../LogoutButton";

const renderedButtons: Array<Record<string, unknown>> = [];

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    fullWidth?: boolean;
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

jest.mock("../../Auth", () => ({
  logout: jest.fn(),
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedLogout = jest.mocked(logout);

describe("LogoutButton", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
    mockedLogout.mockClear();
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
  });

  it("delegates directly to logout", () => {
    const html = renderToStaticMarkup(<LogoutButton />);

    expect(html).toContain("translated:logout");
    expect(renderedButtons[0]).toEqual(
      expect.objectContaining({
        fullWidth: true,
        variant: "tertiary",
      }),
    );

    (renderedButtons[0].onClick as () => void)();
    expect(mockedLogout).toHaveBeenCalledTimes(1);
  });
});
