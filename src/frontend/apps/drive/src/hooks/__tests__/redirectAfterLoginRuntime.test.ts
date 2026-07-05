import {
  DEFAULT_REDIRECT_AFTER_LOGIN_URL,
  resolveRedirectAfterLoginTarget,
} from "../redirectAfterLoginRuntime";

describe("redirectAfterLoginRuntime", () => {
  it("keeps the attempted URL when one is stored", () => {
    expect(
      resolveRedirectAfterLoginTarget("http://192.168.10.123:3000/current"),
    ).toEqual({
      clearAttemptedUrl: true,
      targetUrl: "http://192.168.10.123:3000/current",
    });
  });

  it("falls back to my-files when there is no attempted URL", () => {
    expect(resolveRedirectAfterLoginTarget(null)).toEqual({
      clearAttemptedUrl: false,
      targetUrl: DEFAULT_REDIRECT_AFTER_LOGIN_URL,
    });
  });
});
