import { AppError } from "@/features/errors/AppError";

import { APIError, errorToString } from "../APIError";

jest.mock("@/features/i18n/initI18n", () => ({
  __esModule: true,
  default: {
    t: (key: string) => `translated:${key}`,
  },
}));

describe("APIError", () => {
  it("keeps the API code and optional data payload", () => {
    const error = new APIError(409, { detail: "conflict" });

    expect(error).toBeInstanceOf(Error);
    expect(error.code).toBe(409);
    expect(error.data).toEqual({ detail: "conflict" });
  });

  it("returns raw strings unchanged", () => {
    expect(errorToString("boom")).toBe("boom");
  });

  it("renders APIError string payloads directly", () => {
    expect(errorToString(new APIError(400, "plain backend error"))).toBe(
      "plain backend error",
    );
  });

  it("renders the first structured errors[].detail payload", () => {
    expect(
      errorToString(
        new APIError(400, {
          errors: [
            { detail: "first" },
            { detail: "second" },
          ],
        }),
      ),
    ).toBe("first");
  });

  it("renders flat API object payloads line by line", () => {
    expect(
      errorToString(
        new APIError(400, {
          title: ["The title field is required."],
          detail: "Validation failed.",
        }),
      ),
    ).toBe("The title field is required.\nValidation failed.");
  });

  it("falls back to the translated generic message for APIError without data", () => {
    expect(errorToString(new APIError(500))).toBe(
      "translated:api.error.unexpected",
    );
  });

  it("keeps AppError messages visible", () => {
    expect(errorToString(new AppError("friendly error"))).toBe("friendly error");
  });

  it("falls back to the translated generic message for unknown errors", () => {
    expect(errorToString(new Error("technical stack"))).toBe(
      "translated:api.error.unexpected",
    );
  });
});
