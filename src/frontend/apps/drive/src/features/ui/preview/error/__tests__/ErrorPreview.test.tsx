import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ErrorPreview } from "../ErrorPreview";

const renderedButtons: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => {
    renderedButtons.push({ children, onClick });
    return <button>{children}</button>;
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: () => <span>icon</span>,
  IconType: { OUTLINED: "outlined" },
}));

jest.mock("@/features/explorer/components/icons/ItemIcon", () => ({
  FileIcon: () => <span>file-icon</span>,
}));

const file = {
  id: "file-1",
  title: "Report",
  filename: "Report.txt",
  mimetype: "text/plain",
  size: 12,
};

describe("ErrorPreview", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
  });

  it("shows the download button only when a callback is provided", () => {
    const withoutDownload = renderToStaticMarkup(<ErrorPreview file={file} />);
    const withDownload = renderToStaticMarkup(
      <ErrorPreview file={file} onDownload={jest.fn()} />,
    );

    expect(withoutDownload).not.toContain("file_preview.unsupported.download");
    expect(withDownload).toContain("file_preview.unsupported.download");
  });

  it("routes the action through the provided callback instead of a local side effect", () => {
    const onDownload = jest.fn();

    renderToStaticMarkup(<ErrorPreview file={file} onDownload={onDownload} />);

    const downloadButton = renderedButtons.find(
      (button) => button.children === "file_preview.unsupported.download",
    );

    downloadButton?.onClick?.();

    expect(onDownload).toHaveBeenCalled();
  });
});
