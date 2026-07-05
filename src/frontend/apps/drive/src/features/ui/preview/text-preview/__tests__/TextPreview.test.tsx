import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { TextPreview } from "../TextPreview";

const renderedButtons: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
}> = [];

const renderedCodeMirrorProps: Array<{
  value: string;
  editable: boolean;
  extensions?: unknown[];
  onChange?: (next: string) => void;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("next/dynamic", () => ({
  __esModule: true,
  default: () => (props: {
    value: string;
    editable: boolean;
    extensions?: unknown[];
    onChange?: (next: string) => void;
  }) => {
    renderedCodeMirrorProps.push(props);
    return <div>code-mirror</div>;
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { children?: React.ReactNode; onClick?: () => void }) => {
    renderedButtons.push(props);
    return <button>{props.children}</button>;
  },
}));

jest.mock("@/features/api/APIError", () => ({
  errorToString: (error: unknown) =>
    error instanceof Error ? error.message : String(error),
}));

jest.mock("../textPreviewLanguage", () => ({
  resolveTextPreviewExtensions: jest.fn(() => ["lang-extension"]),
}));

describe("TextPreview", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
    renderedCodeMirrorProps.length = 0;
  });

  it("keeps loading and error/retry states intact", () => {
    const loadingHtml = renderToStaticMarkup(
      <TextPreview
        value=""
        onChange={jest.fn()}
        isEditable={false}
        truncated={false}
        isLoading={true}
      />,
    );

    const retry = jest.fn();
    const errorHtml = renderToStaticMarkup(
      <TextPreview
        value=""
        onChange={jest.fn()}
        isEditable={false}
        truncated={false}
        isLoading={false}
        error={new Error("boom")}
        onRetry={retry}
      />,
    );

    const retryButton = renderedButtons.find(
      (button) => button.children === "common.retry",
    );
    retryButton?.onClick?.();

    expect(loadingHtml).toContain("file_preview.text.loading");
    expect(errorHtml).toContain("boom");
    expect(errorHtml).toContain("common.retry");
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("keeps editability and truncation rules routed through the text surface", () => {
    const onChange = jest.fn();

    const editableHtml = renderToStaticMarkup(
      <TextPreview
        value="const a = 1;"
        onChange={onChange}
        filename="demo.ts"
        isEditable={true}
        truncated={false}
        isLoading={false}
      />,
    );
    const editableProps = renderedCodeMirrorProps[0];
    editableProps?.onChange?.("next-value");

    const truncatedHtml = renderToStaticMarkup(
      <TextPreview
        value="large file"
        onChange={onChange}
        filename="large.txt"
        isEditable={true}
        truncated={true}
        isLoading={false}
      />,
    );
    const truncatedProps = renderedCodeMirrorProps[1];
    truncatedProps?.onChange?.("ignored");

    expect(editableHtml).toContain("code-mirror");
    expect(editableProps).toMatchObject({
      editable: true,
      extensions: ["lang-extension"],
    });
    expect(onChange).toHaveBeenCalledWith("next-value");
    expect(truncatedHtml).toContain("file_preview.text.large_file");
    expect(truncatedProps?.editable).toBe(false);
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});
