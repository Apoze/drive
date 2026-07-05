import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useConfig } from "@/features/config/ConfigProvider";
import { getOperationTimeBound } from "@/features/operations/timeBounds";
import { useTimeBoundedPhase } from "@/features/operations/useTimeBoundedPhase";
import { PreviewPdf } from "../PreviewPdf";

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

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: jest.fn(),
}));

jest.mock("@/features/operations/timeBounds", () => ({
  getOperationTimeBound: jest.fn(),
}));

jest.mock("@/features/operations/useTimeBoundedPhase", () => ({
  useTimeBoundedPhase: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { children?: React.ReactNode; onClick?: () => void }) => {
    renderedButtons.push(props);
    return <button>{props.children}</button>;
  },
}));

const mockedUseConfig = jest.mocked(useConfig);
const mockedGetOperationTimeBound = jest.mocked(getOperationTimeBound);
const mockedUseTimeBoundedPhase = jest.mocked(useTimeBoundedPhase);

describe("PreviewPdf", () => {
  const realUseState = React.useState;
  let useStateSpy: jest.SpiedFunction<typeof React.useState> | undefined;

  beforeEach(() => {
    renderedButtons.length = 0;
    mockedUseConfig.mockReturnValue({ config: {} } as never);
    mockedGetOperationTimeBound.mockReturnValue({
      still_working_ms: 1000,
      fail_ms: 2000,
    });
    mockedUseTimeBoundedPhase.mockReturnValue("loading");
  });

  afterEach(() => {
    useStateSpy?.mockRestore();
  });

  it("renders loading, still-working and failed phases without changing the preview contract", () => {
    const phases: Array<"loading" | "still_working" | "failed"> = [
      "loading",
      "still_working",
      "failed",
    ];

    const outputs = phases.map((phase) => {
      useStateSpy?.mockRestore();
      useStateSpy = jest
        .spyOn(React, "useState")
        .mockImplementation(realUseState as never)
        .mockImplementationOnce((() => [false, jest.fn()]) as never)
        .mockImplementationOnce((() => [0, jest.fn()]) as never);
      mockedUseTimeBoundedPhase.mockReturnValue(phase);
      return renderToStaticMarkup(
        <PreviewPdf src="https://example.test/demo.pdf" />,
      );
    });

    expect(outputs[0]).toContain("file_preview.wopi.loading");
    expect(outputs[1]).toContain("operations.long_running.still_working");
    expect(outputs[2]).toContain("operations.long_running.failed");
    expect(outputs[2]).toContain("common.retry");
  });

  it("keeps the retry action wired to a fresh iframe reload", () => {
    const setLoaded = jest.fn();
    const setReloadKey = jest.fn();

    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementation(realUseState as never)
      .mockImplementationOnce((() => [false, setLoaded]) as never)
      .mockImplementationOnce((() => [3, setReloadKey]) as never);
    mockedUseTimeBoundedPhase.mockReturnValue("failed");

    const html = renderToStaticMarkup(
      <PreviewPdf src="https://example.test/demo.pdf" />,
    );
    const retryButton = renderedButtons.find(
      (button) => button.children === "common.retry",
    );

    retryButton?.onClick?.();

    expect(html).toContain("src=\"https://example.test/demo.pdf\"");
    expect(setLoaded).toHaveBeenCalledWith(false);
    expect(setReloadKey).toHaveBeenCalled();
  });
});
