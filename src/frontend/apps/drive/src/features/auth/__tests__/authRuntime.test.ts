import { APIError } from "@/features/api/APIError";

import { resolveAuthInitOutcome, syncPosthogIdentity } from "../authRuntime";

describe("authRuntime", () => {
  it("returns the fetched user on success", async () => {
    const user = { email: "jane@example.test", id: "user-1" } as never;

    await expect(
      resolveAuthInitOutcome({
        attemptSilentLogin: jest.fn(),
        canAttemptSilentLogin: jest.fn(() => true),
        fetchMe: jest.fn(async () => user),
        silentLoginEnabled: true,
      }),
    ).resolves.toEqual({
      kind: "user",
      user,
    });
  });

  it("starts silent login on 401 when allowed", async () => {
    const attemptSilentLogin = jest.fn();

    await expect(
      resolveAuthInitOutcome({
        attemptSilentLogin,
        canAttemptSilentLogin: jest.fn(() => true),
        fetchMe: jest.fn(async () => {
          throw new APIError(401);
        }),
        silentLoginEnabled: true,
      }),
    ).resolves.toEqual({
      kind: "silent-login",
    });

    expect(attemptSilentLogin).toHaveBeenCalledWith(30);
  });

  it("falls back to anonymous when silent login is disabled or not allowed", async () => {
    await expect(
      resolveAuthInitOutcome({
        attemptSilentLogin: jest.fn(),
        canAttemptSilentLogin: jest.fn(() => false),
        fetchMe: jest.fn(async () => {
          throw new APIError(401);
        }),
        silentLoginEnabled: true,
      }),
    ).resolves.toEqual({
      kind: "anonymous",
    });
  });

  it("falls back to anonymous on non-401 errors", async () => {
    await expect(
      resolveAuthInitOutcome({
        attemptSilentLogin: jest.fn(),
        canAttemptSilentLogin: jest.fn(() => true),
        fetchMe: jest.fn(async () => {
          throw new Error("boom");
        }),
        silentLoginEnabled: true,
      }),
    ).resolves.toEqual({
      kind: "anonymous",
    });
  });

  it("identifies the user in posthog when an email is available", () => {
    const identify = jest.fn();

    syncPosthogIdentity({ identify }, { email: "jane@example.test" } as never);

    expect(identify).toHaveBeenCalledWith("jane@example.test", {
      email: "jane@example.test",
    });
  });

  it("does nothing when there is no user email", () => {
    const identify = jest.fn();

    syncPosthogIdentity({ identify }, null);

    expect(identify).not.toHaveBeenCalled();
  });
});
