import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useAuth } from "@/features/auth/Auth";
import { UserProfile } from "../UserProfile";

const renderedUserMenus: Array<Record<string, unknown>> = [];
let loginButtonRenderCount = 0;

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  UserMenu: (props: {
    user: { full_name?: string };
    actions?: React.ReactNode;
  }) => (
    <div>
      {renderedUserMenus.push(props as Record<string, unknown>) && null}
      user-menu:{props.user.full_name}
      {props.actions}
    </div>
  ),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
  logout: jest.fn(),
}));

jest.mock("@/features/layouts/components/header/Header", () => ({
  LanguagePickerUserMenu: () => <div>language-picker</div>,
}));

jest.mock("@/features/auth/components/LoginButton", () => ({
  LoginButton: () => {
    loginButtonRenderCount += 1;
    return <div>login-button</div>;
  },
}));

const mockedUseAuth = jest.mocked(useAuth);

describe("UserProfile", () => {
  beforeEach(() => {
    renderedUserMenus.length = 0;
    loginButtonRenderCount = 0;
  });

  it("renders the user menu branch when a user is available", () => {
    mockedUseAuth.mockReturnValue({
      user: {
        full_name: "Jane Doe",
      },
    } as never);

    const html = renderToStaticMarkup(<UserProfile />);

    expect(html).toContain("user-menu:Jane Doe");
    expect(html).toContain("language-picker");
    expect(loginButtonRenderCount).toBe(0);
    expect(renderedUserMenus).toHaveLength(1);
  });

  it("renders the login button branch for anonymous users", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
    } as never);

    const html = renderToStaticMarkup(<UserProfile />);

    expect(html).toContain("login-button");
    expect(renderedUserMenus).toHaveLength(0);
    expect(loginButtonRenderCount).toBe(1);
  });
});
