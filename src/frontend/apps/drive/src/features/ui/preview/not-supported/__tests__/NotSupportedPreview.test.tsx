import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { NotSupportedPreview } from "../NotSupportedPreview";

const renderedButtons: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
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

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { children?: React.ReactNode; onClick?: () => void }) => {
    renderedButtons.push(props);
    return <button>{props.children}</button>;
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: ({ name }: { name: string }) => <span>{name}</span>,
  IconType: {
    OUTLINED: "outlined",
  },
}));

jest.mock("@/features/explorer/components/icons/ItemIcon", () => ({
  FileIcon: () => <div>file-icon</div>,
}));

const file = {
  id: "file-1",
  size: 128,
  title: "Demo",
  filename: "Demo.txt",
  mimetype: "text/plain",
};

describe("NotSupportedPreview", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
  });

  it("keeps default fallback copy and optional download CTA intact", () => {
    const onDownload = jest.fn();
    const html = renderToStaticMarkup(
      <NotSupportedPreview file={file} onDownload={onDownload} />,
    );

    const downloadButton = renderedButtons.find(
      (button) => button.children === "file_preview.suspicious.download",
    );
    downloadButton?.onClick?.();

    expect(html).toContain("file-icon");
    expect(html).toContain("file_preview.unsupported.title");
    expect(html).toContain("file_preview.unsupported.description");
    expect(html).toContain("file_preview.suspicious.download");
    expect(onDownload).toHaveBeenCalledWith(file);
  });

  it("accepts custom title and description without changing the fallback surface", () => {
    const html = renderToStaticMarkup(
      <NotSupportedPreview
        file={file}
        title="custom-title"
        description="custom-description"
      />,
    );

    expect(html).toContain("custom-title");
    expect(html).toContain("custom-description");
  });
});
