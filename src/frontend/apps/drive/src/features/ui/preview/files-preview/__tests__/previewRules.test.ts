import { MimeCategory } from "@/features/explorer/utils/mimeTypes";
import {
  getPreviewMimeCategory,
  isArchiveEligibleByRules,
  isTextEligibleByRules,
} from "../previewRules";

describe("previewRules (viewer selection)", () => {
  it(".zip should be eligible for the archive viewer", () => {
    expect(isArchiveEligibleByRules("application/octet-stream", "backup.zip")).toBe(
      true,
    );
    expect(getPreviewMimeCategory("application/octet-stream", "backup.zip")).toBe(
      MimeCategory.ARCHIVE,
    );
  });

  it(".inf should be eligible for the text viewer", () => {
    expect(isTextEligibleByRules("application/octet-stream", "oemsetup.inf")).toBe(
      true,
    );
  });

  it(".sys should never be treated as archive or text by filename rules", () => {
    expect(getPreviewMimeCategory("application/octet-stream", "driver.sys")).not.toBe(
      MimeCategory.ARCHIVE,
    );
    expect(isTextEligibleByRules("application/octet-stream", "driver.sys")).toBe(
      false,
    );
  });

  it(".tar.gz should be eligible for the archive viewer (multi-extension)", () => {
    expect(
      isArchiveEligibleByRules("application/octet-stream", "backup.tar.gz"),
    ).toBe(true);
  });

  it(".gz should not be eligible for the archive viewer (single-file compression)", () => {
    expect(isArchiveEligibleByRules("application/octet-stream", "backup.gz")).toBe(
      false,
    );
  });
});
