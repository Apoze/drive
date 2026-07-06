import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/router";
import { useQuery } from "@tanstack/react-query";
import { getDriver } from "@/features/config/Config";
import { useConfig } from "@/features/config/ConfigProvider";
import { APIError, errorToString } from "@/features/api/APIError";
import { getOperationTimeBound } from "@/features/operations/timeBounds";
import { useTimeBoundedPhase } from "@/features/operations/useTimeBoundedPhase";

import MountWopiPage from "@/pages/explorer/mounts/[mount_id]/wopi";

const renderedButtonProps: Array<{
  onClick?: () => void;
}> = [];

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("next/link", () => ({
  __esModule: true,
  default: ({
    href,
    children,
  }: {
    href: string;
    children?: React.ReactNode;
  }) => <a href={href}>{children}</a>,
}));

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { onClick?: () => void; children?: React.ReactNode }) => {
    renderedButtonProps.push(props);
    return <button>{props.children}</button>;
  },
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
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

jest.mock("@/features/layouts/components/explorer/ExplorerLayout", () => ({
  getGlobalExplorerLayout: jest.fn((page) => page),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
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
  errorToString: jest.fn(() => "api.error.unexpected"),
}));

const mockedUseRouter = jest.mocked(useRouter);
const mockedUseQuery = jest.mocked(useQuery);
const mockedGetDriver = jest.mocked(getDriver);
const mockedUseConfig = jest.mocked(useConfig);
const mockedGetOperationTimeBound = jest.mocked(getOperationTimeBound);
const mockedUseTimeBoundedPhase = jest.mocked(useTimeBoundedPhase);
const mockedErrorToString = jest.mocked(errorToString);

describe("MountWopiPage", () => {
  const push = jest.fn();
  const refetch = jest.fn();
  const getMountWopiInfo = jest.fn();

  beforeEach(() => {
    renderedButtonProps.length = 0;
    push.mockReset();
    refetch.mockReset();
    getMountWopiInfo.mockReset();
    mockedUseQuery.mockReset();
    mockedUseRouter.mockReturnValue({
      query: {
        mount_id: "mount-1",
        path: "/docs/file.docx",
      },
      push,
    } as never);
    mockedUseConfig.mockReturnValue({
      config: { FRONTEND_OPERATION_TIME_BOUNDS_MS: {} },
    } as never);
    mockedGetOperationTimeBound.mockReturnValue({
      still_working_ms: 1000,
      fail_ms: 2000,
    });
    mockedUseTimeBoundedPhase.mockReset();
    mockedUseTimeBoundedPhase
      .mockReturnValueOnce("loading")
      .mockReturnValueOnce("loading");
    mockedGetDriver.mockReturnValue({
      getMountWopiInfo,
    } as never);
    mockedUseQuery.mockImplementation(
      () =>
        ({
          data: {
            access_token: "token-1",
            access_token_ttl: 3600,
            launch_url: "https://office.example.test/launch",
          },
          isLoading: false,
          isError: false,
          error: null,
          refetch,
        }) as never,
    );
    mockedErrorToString.mockReset();
    mockedErrorToString.mockReturnValue("fallback-error");
  });

  it("renders the missing params branch", () => {
    mockedUseRouter.mockReturnValue({
      query: {},
      push,
    } as never);

    const html = renderToStaticMarkup(<MountWopiPage />);

    expect(html).toContain("explorer.mounts.preview_page.missing_params");
    expect(html).toContain("/explorer/mounts");
  });

  it("wires the WOPI query and loading/still-working phases", async () => {
    mockedUseQuery.mockImplementation(
      () =>
        ({
          data: undefined,
          isLoading: true,
          isError: false,
          error: null,
          refetch,
        }) as never,
    );
    mockedUseTimeBoundedPhase.mockReset();
    mockedUseTimeBoundedPhase
      .mockReturnValueOnce("loading")
      .mockReturnValueOnce("loading");

    renderToStaticMarkup(<MountWopiPage />);

    const queryConfig = mockedUseQuery.mock.calls[0][0] as {
      queryKey: Array<string>;
      enabled: boolean;
      refetchOnWindowFocus: boolean;
      queryFn: () => Promise<unknown>;
    };
    expect(queryConfig.queryKey).toEqual([
      "mounts",
      "mount-1",
      "wopi",
      "/docs/file.docx",
    ]);
    expect(queryConfig.enabled).toBe(true);
    expect(queryConfig.refetchOnWindowFocus).toBe(false);

    getMountWopiInfo.mockResolvedValue("wopi-info");
    await expect(queryConfig.queryFn()).resolves.toBe("wopi-info");
    expect(getMountWopiInfo).toHaveBeenCalledWith({
      mountId: "mount-1",
      path: "/docs/file.docx",
    });

    mockedUseTimeBoundedPhase.mockReset();
    mockedUseTimeBoundedPhase
      .mockReturnValueOnce("still_working")
      .mockReturnValueOnce("loading");
    const stillWorkingHtml = renderToStaticMarkup(<MountWopiPage />);
    expect(stillWorkingHtml).toContain("operations.long_running.still_working");
  });

  it("maps WOPI unavailable errors and fallback errors coherently", () => {
    mockedUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new APIError(400, {
        errors: [{ code: "wopi.discovery_missing" }],
      }),
      refetch,
    } as never);

    const unavailableHtml = renderToStaticMarkup(<MountWopiPage />);
    expect(unavailableHtml).toContain("file_preview.wopi.unavailable.discovery_missing");

    mockedUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("boom"),
      refetch,
    } as never);

    const fallbackHtml = renderToStaticMarkup(<MountWopiPage />);
    expect(fallbackHtml).toContain("fallback-error");
    expect(mockedErrorToString).toHaveBeenCalled();
  });

  it("renders the WOPI form, submits it and keeps the back action wired", () => {
    const submit = jest.fn();
    const useEffectSpy = jest.spyOn(React, "useEffect");
    const useRefSpy = jest.spyOn(React, "useRef");
    const useStateSpy = jest.spyOn(React, "useState");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    useRefSpy.mockReturnValue({
      current: {
        submit,
      },
    } as never);
    useStateSpy
      .mockImplementationOnce((() => [true, jest.fn()]) as never)
      .mockImplementationOnce((() => [0, jest.fn()]) as never);

    const html = renderToStaticMarkup(<MountWopiPage />);
    renderedButtonProps[0]?.onClick?.();

    expect(submit).toHaveBeenCalledTimes(1);
    expect(html).toContain('action="https://office.example.test/launch"');
    expect(html).toContain('name="access_token"');
    expect(html).toContain('value="token-1"');
    expect(html).toContain('title="file.docx"');
    expect(push).toHaveBeenCalledWith({
      pathname: "/explorer/mounts/[mount_id]",
      query: {
        mount_id: "mount-1",
        path: "/docs",
      },
    });

    useRefSpy.mockRestore();
    useEffectSpy.mockRestore();
    useStateSpy.mockRestore();
  });

  it("renders iframe retry when the iframe phase fails", () => {
    const setIframeLoaded = jest.fn();
    const setIframeKey = jest.fn();
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy
      .mockImplementationOnce((() => [false, setIframeLoaded]) as never)
      .mockImplementationOnce((() => [0, setIframeKey]) as never);
    mockedUseTimeBoundedPhase.mockReset();
    mockedUseTimeBoundedPhase
      .mockReturnValueOnce("loading")
      .mockReturnValueOnce("failed");

    const html = renderToStaticMarkup(<MountWopiPage />);
    renderedButtonProps[1]?.onClick?.();

    expect(html).toContain("operations.long_running.failed");
    expect(setIframeKey).toHaveBeenCalledWith(expect.any(Function));
    expect(refetch).toHaveBeenCalledTimes(1);

    useStateSpy.mockRestore();
  });
});
