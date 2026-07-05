import { loadLanguage } from "@uiw/codemirror-extensions-langs";
import {
  getTextPreviewExtensionFromFilename,
  resolveTextPreviewExtensions,
} from "../textPreviewLanguage";

jest.mock("@uiw/codemirror-extensions-langs", () => ({
  loadLanguage: jest.fn(),
}));

const mockedLoadLanguage = jest.mocked(loadLanguage);

describe("textPreviewLanguage", () => {
  beforeEach(() => {
    mockedLoadLanguage.mockReset();
  });

  it("resolves file extensions and loads the matching CodeMirror language when supported", () => {
    const extension = { name: "typescript-extension" } as never;
    mockedLoadLanguage.mockReturnValue(extension);

    expect(getTextPreviewExtensionFromFilename("demo.TSX")).toBe("tsx");
    expect(resolveTextPreviewExtensions("demo.TSX")).toEqual([extension]);
    expect(mockedLoadLanguage).toHaveBeenCalledWith("tsx");
  });

  it("fails closed when no filename or no language mapping is available", () => {
    expect(getTextPreviewExtensionFromFilename("README")).toBeNull();
    expect(resolveTextPreviewExtensions("README")).toEqual([]);
    expect(resolveTextPreviewExtensions("archive.unknown")).toEqual([]);
    expect(mockedLoadLanguage).not.toHaveBeenCalled();
  });
});
