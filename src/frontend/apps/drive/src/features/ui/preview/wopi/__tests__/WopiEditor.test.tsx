import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useQuery } from "@tanstack/react-query";
import { WopiEditor } from "../WopiEditor";
import { APIError } from "@/features/api/APIError";

const capturedErrorPreviewProps: Array<{
  onDownload?: () => void;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
  useQueryClient: jest.fn(() => ({})),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({ children }: { children?: React.ReactNode }) => (
    <button>{children}</button>
  ),
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: () => ({ config: {} }),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: () => ({
    getWopiInfo: jest.fn(),
  }),
}));

jest.mock("@/features/operations/timeBounds", () => ({
  getOperationTimeBound: jest.fn(() => ({
    still_working_ms: 1000,
    fail_ms: 2000,
  })),
}));

jest.mock("@/features/operations/useTimeBoundedPhase", () => ({
  useTimeBoundedPhase: jest.fn(() => "loading"),
}));

jest.mock("@/features/api/APIError", () => ({
  APIError: class APIError extends Error {
    code: number;
    data?: unknown;

    constructor(code: number, data?: unknown) {
      super();
      this.code = code;
      this.data = data;
    }
  },
  errorToString: () => "error",
}));

jest.mock("@/features/ui/preview/error/ErrorPreview", () => ({
  ErrorPreview: (props: { onDownload?: () => void }) => {
    capturedErrorPreviewProps.push(props);
    return <div>error-preview</div>;
  },
}));

const mockedUseQuery = jest.mocked(useQuery);

const item = {
  id: "file-1",
  title: "Report",
  filename: "Report.txt",
  mimetype: "text/plain",
  size: 12,
};

describe("WopiEditor", () => {
  beforeEach(() => {
    capturedErrorPreviewProps.length = 0;
    mockedUseQuery.mockReset();
    mockedUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new APIError(500, {
        errors: [{ code: "wopi.file_unavailable" }],
      }),
      refetch: jest.fn(),
    } as never);
  });

  it("forwards the preview download callback to the shared error fallback", () => {
    const onDownload = jest.fn();

    renderToStaticMarkup(<WopiEditor item={item} onDownload={onDownload} />);

    expect(capturedErrorPreviewProps).toHaveLength(1);
    expect(capturedErrorPreviewProps[0].onDownload).toBe(onDownload);
  });
});
