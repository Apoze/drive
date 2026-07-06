import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/router";
import { useQuery } from "@tanstack/react-query";
import { fetchAPI } from "@/features/api/fetchApi";
import { getOrigin } from "@/features/api/utils";

import MountPreviewPage from "@/pages/explorer/mounts/[mount_id]/preview";

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

jest.mock("@/features/api/fetchApi", () => ({
  fetchAPI: jest.fn(),
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
}));

jest.mock("@/features/api/utils", () => ({
  getOrigin: jest.fn(),
}));

jest.mock("@/features/layouts/components/explorer/ExplorerLayout", () => ({
  getGlobalExplorerLayout: jest.fn((page) => page),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

const mockedUseRouter = jest.mocked(useRouter);
const mockedUseQuery = jest.mocked(useQuery);
const mockedFetchAPI = jest.mocked(fetchAPI);
const mockedGetOrigin = jest.mocked(getOrigin);
const { APIError } = jest.requireMock("@/features/api/APIError") as {
  APIError: new (code: number, data?: unknown) => Error;
};

describe("MountPreviewPage", () => {
  const push = jest.fn();
  const reload = jest.fn();

  beforeEach(() => {
    renderedButtonProps.length = 0;
    push.mockReset();
    reload.mockReset();
    mockedUseQuery.mockReset();
    mockedUseRouter.mockReturnValue({
      query: {
        mount_id: "mount-1",
        path: "/docs/file.png",
      },
      push,
      reload,
    } as never);
    mockedUseQuery.mockImplementation(
      () =>
        ({
          data: {
            contentType: "image/png",
            apiUrl: "/api/v1.0/mounts/mount-1/preview/?path=%2Fdocs%2Ffile.png",
            downloadUrl:
              "/api/v1.0/mounts/mount-1/download/?path=%2Fdocs%2Ffile.png",
          },
          isLoading: false,
          error: null,
        }) as never,
    );
    mockedFetchAPI.mockReset();
    mockedGetOrigin.mockReset();
  });

  it("renders the missing params branch", () => {
    mockedUseRouter.mockReturnValue({
      query: {},
      push,
      reload,
    } as never);

    const html = renderToStaticMarkup(<MountPreviewPage />);

    expect(html).toContain("explorer.mounts.preview_page.missing_params");
    expect(html).toContain("/explorer/mounts");
  });

  it("wires the preview query, range preflight and resulting URLs", async () => {
    mockedGetOrigin.mockReturnValue("http://api.example.test");
    const cancel = jest.fn().mockResolvedValue(undefined);
    mockedFetchAPI.mockResolvedValue({
      headers: {
        get: jest.fn(() => "image/png"),
      },
      body: {
        cancel,
      },
    } as never);

    renderToStaticMarkup(<MountPreviewPage />);

    const queryConfig = mockedUseQuery.mock.calls[0][0] as {
      queryKey: Array<string>;
      enabled: boolean;
      refetchOnWindowFocus: boolean;
      queryFn: () => Promise<{
        contentType: string;
        apiUrl: string;
        downloadUrl: string;
      }>;
    };
    expect(queryConfig.queryKey).toEqual([
      "mounts",
      "preview",
      "mount-1",
      "/docs/file.png",
    ]);
    expect(queryConfig.enabled).toBe(true);
    expect(queryConfig.refetchOnWindowFocus).toBe(false);

    await expect(queryConfig.queryFn()).resolves.toEqual({
      contentType: "image/png",
      apiUrl:
        "http://api.example.test/api/v1.0/mounts/mount-1/preview/?path=%2Fdocs%2Ffile.png",
      downloadUrl:
        "http://api.example.test/api/v1.0/mounts/mount-1/download/?path=%2Fdocs%2Ffile.png",
    });
    expect(mockedFetchAPI).toHaveBeenCalledWith(
      "mounts/mount-1/preview/",
      {
        params: { path: "/docs/file.png" },
        headers: { Range: "bytes=0-0" },
      },
      { redirectOn40x: false },
    );
    expect(cancel).toHaveBeenCalledWith();
  });

  it("maps preview unavailable errors to the back action", () => {
    mockedUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new APIError(400, {
        errors: [{ code: "mount.preview.not_previewable" }],
      }),
    } as never);

    const html = renderToStaticMarkup(<MountPreviewPage />);
    renderedButtonProps[0]?.onClick?.();

    expect(html).toContain("explorer.mounts.preview_page.not_available");
    expect(html).toContain("explorer.mounts.preview_page.next_action");
    expect(push).toHaveBeenCalledWith({
      pathname: "/explorer/mounts/[mount_id]",
      query: {
        mount_id: "mount-1",
        path: "/docs",
      },
    });
  });

  it("maps preview access denied separately", () => {
    mockedUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new APIError(403, {
        errors: [{ code: "mount.smb.env.auth_failed" }],
      }),
    } as never);

    const html = renderToStaticMarkup(<MountPreviewPage />);

    expect(html).toContain("explorer.mounts.preview_page.access_denied");
  });

  it("renders the generic error branch with retry and back buttons", () => {
    mockedUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("boom"),
    } as never);

    const html = renderToStaticMarkup(<MountPreviewPage />);
    renderedButtonProps[0]?.onClick?.();
    renderedButtonProps[1]?.onClick?.();

    expect(html).toContain("explorer.mounts.preview_page.error");
    expect(reload).toHaveBeenCalledTimes(1);
    expect(push).toHaveBeenCalledWith({
      pathname: "/explorer/mounts/[mount_id]",
      query: {
        mount_id: "mount-1",
        path: "/docs",
      },
    });
  });

  it("renders image previews and non-image previews with the expected URLs", () => {
    const imageHtml = renderToStaticMarkup(<MountPreviewPage />);
    expect(imageHtml).toContain(
      'href="/api/v1.0/mounts/mount-1/preview/?path=%2Fdocs%2Ffile.png"',
    );
    expect(imageHtml).toContain(
      'href="/api/v1.0/mounts/mount-1/download/?path=%2Fdocs%2Ffile.png"',
    );
    expect(imageHtml).toContain("<img");

    mockedUseQuery.mockReturnValue({
      data: {
        contentType: "application/pdf",
        apiUrl: "/api/v1.0/mounts/mount-1/preview/?path=%2Fdocs%2Ffile.pdf",
        downloadUrl:
          "/api/v1.0/mounts/mount-1/download/?path=%2Fdocs%2Ffile.pdf",
      },
      isLoading: false,
      error: null,
    } as never);

    const iframeHtml = renderToStaticMarkup(<MountPreviewPage />);
    expect(iframeHtml).toContain("<iframe");
  });
});
