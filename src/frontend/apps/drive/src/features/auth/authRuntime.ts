import { APIError } from "../api/APIError";
import { User } from "./types";

type PosthogClient = {
  identify: (distinctId: string, properties?: Record<string, unknown>) => void;
};

type AuthInitOutcome =
  | { kind: "user"; user: User }
  | { kind: "anonymous" }
  | { kind: "silent-login" };

export const resolveAuthInitOutcome = async ({
  attemptSilentLogin,
  canAttemptSilentLogin,
  fetchMe,
  silentLoginEnabled,
}: {
  attemptSilentLogin: (retryIntervalInSeconds: number) => void;
  canAttemptSilentLogin: () => boolean;
  fetchMe: () => Promise<User>;
  silentLoginEnabled?: boolean;
}): Promise<AuthInitOutcome> => {
  try {
    const user = await fetchMe();
    return { kind: "user", user };
  } catch (error) {
    if (
      silentLoginEnabled &&
      error instanceof APIError &&
      error.code === 401 &&
      canAttemptSilentLogin()
    ) {
      attemptSilentLogin(30);
      return { kind: "silent-login" };
    }

    return { kind: "anonymous" };
  }
};

export const syncPosthogIdentity = (
  posthog: PosthogClient,
  user?: Pick<User, "email"> | null,
) => {
  if (!user?.email) {
    return;
  }

  posthog.identify(user.email, {
    email: user.email,
  });
};
