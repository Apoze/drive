import { APIError } from "@/features/api/APIError";
import { Query } from "@tanstack/react-query";

export const shouldDisplayGlobalErrorToast = (
  error: Error,
  query: Pick<Query, "meta"> | undefined,
) => {
  if (query?.meta?.noGlobalError) {
    return false;
  }

  if (error instanceof APIError) {
    if (error.code === 401) {
      return false;
    }

    if (error.code === 403 && !query?.meta?.showErrorOn403) {
      return false;
    }
  }

  return true;
};
