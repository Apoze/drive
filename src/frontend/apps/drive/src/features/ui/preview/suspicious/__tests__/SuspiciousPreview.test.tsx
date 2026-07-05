import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SuspiciousPreview } from "../SuspiciousPreview";

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

describe("SuspiciousPreview", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
  });

  it("keeps the suspicious fallback and optional download CTA intact", () => {
    const handleDownload = jest.fn();
    const html = renderToStaticMarkup(
      <SuspiciousPreview handleDownload={handleDownload} />,
    );

    const downloadButton = renderedButtons.find(
      (button) => button.children === "file_preview.unsupported.download",
    );
    downloadButton?.onClick?.();

    expect(html).toContain("file_preview.suspicious.title");
    expect(html).toContain("file_preview.suspicious.description");
    expect(html).toContain("file_preview.unsupported.download");
    expect(handleDownload).toHaveBeenCalledTimes(1);
  });

  it("renders without CTA when no download callback is provided", () => {
    const html = renderToStaticMarkup(<SuspiciousPreview />);

    expect(html).not.toContain("file_preview.unsupported.download");
  });
});
