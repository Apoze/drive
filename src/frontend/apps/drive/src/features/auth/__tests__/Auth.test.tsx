import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useConfig } from "@/features/config/ConfigProvider";

import { Auth } from "../Auth";

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: jest.fn(),
}));

jest.mock("@/features/ui/components/spinner/SpinnerPage", () => ({
  SpinnerPage: () => <div>spinner-page</div>,
}));

jest.mock("posthog-js", () => ({
  posthog: {
    identify: jest.fn(),
    reset: jest.fn(),
  },
}));

const mockedUseConfig = jest.mocked(useConfig);

describe("Auth", () => {
  beforeEach(() => {
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_SILENT_LOGIN_ENABLED: true,
      },
    } as never);
  });

  it("renders the shared spinner while auth is still unresolved", () => {
    const html = renderToStaticMarkup(
      <Auth>
        <div>protected-content</div>
      </Auth>,
    );

    expect(html).toContain("spinner-page");
    expect(html).not.toContain("protected-content");
  });

  it("renders children once auth is already resolved", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy.mockReturnValueOnce([null, jest.fn()] as never);

    const html = renderToStaticMarkup(
      <Auth>
        <div>protected-content</div>
      </Auth>,
    );

    expect(html).toContain("protected-content");
    expect(html).not.toContain("spinner-page");

    useStateSpy.mockRestore();
  });
});
