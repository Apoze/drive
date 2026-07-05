import { AppError } from "../AppError";

describe("AppError", () => {
  it("extends Error and keeps the provided message", () => {
    const error = new AppError("friendly");

    expect(error).toBeInstanceOf(Error);
    expect(error.message).toBe("friendly");
  });
});
