import { AppError } from "../AppError";
import { UploadError } from "../UploadError";

describe("UploadError", () => {
  it("extends AppError and keeps kind/nextAction/itemId", () => {
    const error = new UploadError({
      itemId: "item-1",
      kind: "put_failed",
      message: "Upload failed",
      nextAction: "retry",
    });

    expect(error).toBeInstanceOf(AppError);
    expect(error.message).toBe("Upload failed");
    expect(error.kind).toBe("put_failed");
    expect(error.nextAction).toBe("retry");
    expect(error.itemId).toBe("item-1");
  });
});
