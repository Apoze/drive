import { APIError } from "@/features/api/APIError";

export const getPublicShareError = (
  error: unknown,
): "not_found" | "timeout" | "unknown" => {
  if (error instanceof APIError && error.code === 404) {
    return "not_found";
  }
  if (error instanceof Error && error.message.toLowerCase().includes("timeout")) {
    return "timeout";
  }
  return "unknown";
};

export const getPublicMountShareError = (
  error: unknown,
): "not_found" | "gone" | "timeout" | "unknown" => {
  if (error instanceof APIError && error.code === 404) {
    return "not_found";
  }
  if (error instanceof APIError && error.code === 410) {
    return "gone";
  }
  if (error instanceof Error && error.message.toLowerCase().includes("timeout")) {
    return "timeout";
  }
  return "unknown";
};
