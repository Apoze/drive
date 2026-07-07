import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useAuth } from "@/features/auth/Auth";
import { UserProfile } from "../UserProfile";

const renderedUserMenus: Array<Record<string, unknown>> = [];
const renderedDropdowns: Array<Record<string, unknown>> = [];
const renderedButtons: Array<Record<string, unknown>> = [];
const copyToClipboard = jest.fn();
const changeLanguage = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {
      changeLanguage,
    },
  }),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  DropdownMenu: ({
    children,
    options,
  }: {
    children?: React.ReactNode;
    options: Array<{ label: string; children?: Array<{ label: string }> }>;
  }) => (
    <div>
      {renderedDropdowns.push({ options }) && null}
      {children}
      {options.map((option) => (
        <div key={option.label}>
          {option.label}
          {option.children?.map((child) => (
            <span key={child.label}>{child.label}</span>
          ))}
        </div>
      ))}
    </div>
  ),
  Icon: ({ name }: { name: string }) => <span>icon:{name}</span>,
  IconSize: {
    SMALL: "small",
  },
  useDropdownMenu: () => ({
    isOpen: false,
    setIsOpen: jest.fn(),
  }),
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

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({
    children,
    ...props
  }: {
    children?: React.ReactNode;
    [key: string]: unknown;
  }) => {
    renderedButtons.push(props);
    return <button>{children}</button>;
  },
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
  logout: jest.fn(),
}));

jest.mock("@/features/layouts/components/header/Header", () => ({
  LANGUAGES: [
    { label: "Français", value: "fr-fr" },
    { label: "English", value: "en-us" },
  ],
  LanguagePickerUserMenu: () => <div>language-picker</div>,
}));

jest.mock("@/features/ui/components/anonymous-cta/AnonymousCTA", () => ({
  AnonymousCTA: () => <div>anonymous-cta</div>,
}));

jest.mock("@/hooks/useCopyToClipboard", () => ({
  useClipboard: () => copyToClipboard,
}));

const mockedUseAuth = jest.mocked(useAuth);

describe("UserProfile", () => {
  beforeEach(() => {
    renderedUserMenus.length = 0;
    renderedDropdowns.length = 0;
    renderedButtons.length = 0;
    copyToClipboard.mockReset();
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
    expect(html).not.toContain("anonymous-cta");
    expect(renderedUserMenus).toHaveLength(1);
    expect(renderedDropdowns).toHaveLength(0);
  });

  it("renders the anonymous dropdown and CTA branch for anonymous users", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
    } as never);

    const html = renderToStaticMarkup(<UserProfile />);

    expect(html).toContain("anonymous-cta");
    expect(html).toContain("anonymous_dropdown_menu.copy_link");
    expect(html).toContain("anonymous_dropdown_menu.languages");
    expect(html).toContain("Français");
    expect(renderedUserMenus).toHaveLength(0);
    expect(renderedDropdowns).toHaveLength(1);
    expect(renderedButtons).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          "data-testid": "anonymous-dropdown-menu",
        }),
      ]),
    );
  });
});
