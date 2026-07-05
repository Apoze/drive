import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useResponsive } from "@gouvfr-lasuite/ui-kit";
import { LeftPanelMobile } from "../LeftPanelMobile";

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  useResponsive: jest.fn(),
}));

jest.mock("@/features/ui/components/gaufre/Gaufre", () => ({
  Gaufre: () => <div>gaufre</div>,
}));

jest.mock("@/features/ui/components/user/UserProfile", () => ({
  UserProfile: () => <div>user-profile</div>,
}));

const mockedUseResponsive = jest.mocked(useResponsive);

describe("LeftPanelMobile", () => {
  it("stays hidden outside tablet mode", () => {
    mockedUseResponsive.mockReturnValue({
      isTablet: false,
    } as never);

    expect(renderToStaticMarkup(<LeftPanelMobile />)).toBe("");
  });

  it("keeps the canonical gaufre and user profile wiring on tablet", () => {
    mockedUseResponsive.mockReturnValue({
      isTablet: true,
    } as never);

    const html = renderToStaticMarkup(<LeftPanelMobile />);

    expect(html).toContain("gaufre");
    expect(html).toContain("user-profile");
  });
});
