export const DEFAULT_REDIRECT_AFTER_LOGIN_URL = "/explorer/items/my-files";

export const resolveRedirectAfterLoginTarget = (
  attemptedUrl: string | null | undefined,
) => {
  if (attemptedUrl) {
    return {
      clearAttemptedUrl: true,
      targetUrl: attemptedUrl,
    };
  }

  return {
    clearAttemptedUrl: false,
    targetUrl: DEFAULT_REDIRECT_AFTER_LOGIN_URL,
  };
};
