import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { GlobalLayout } from "../GlobalLayout";

jest.mock("@/features/auth/Auth", () => ({
  Auth: ({ children }: { children?: React.ReactNode }) => (
    <div>auth-wrapper{children}</div>
  ),
}));

describe("GlobalLayout", () => {
  it("wraps children with the canonical Auth provider", () => {
    const html = renderToStaticMarkup(
      <GlobalLayout>
        <div>app-content</div>
      </GlobalLayout>,
    );

    expect(html).toContain("auth-wrapper");
    expect(html).toContain("app-content");
  });
});
