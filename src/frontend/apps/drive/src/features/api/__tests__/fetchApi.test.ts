import { APIError } from "../APIError";
import { AppError } from "@/features/errors/AppError";
import {
  ensureCsrfCookie,
  fetchAPI,
  getCSRFToken,
} from "../fetchApi";

jest.mock("@/features/i18n/initI18n", () => ({
  __esModule: true,
  default: {
    t: (key: string) => `translated:${key}`,
  },
}));

describe("fetchApi", () => {
  const originalFetch = global.fetch;
  const originalWindow = global.window;
  const originalDocument = global.document;
  const originalSessionStorage = global.sessionStorage;
  const originalApiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN;
  const setItem = jest.fn();

  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_ORIGIN = "http://api.example.test";
    setItem.mockReset();

    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          href: "http://192.168.10.123:3000/explorer/items/my-files",
        },
      },
    });
    Object.defineProperty(global, "document", {
      configurable: true,
      value: {
        cookie: "",
      },
    });
    Object.defineProperty(global, "sessionStorage", {
      configurable: true,
      value: {
        setItem,
      },
    });

    global.fetch = jest.fn();
  });

  afterEach(() => {
    process.env.NEXT_PUBLIC_API_ORIGIN = originalApiOrigin;
    global.fetch = originalFetch;

    if (originalWindow === undefined) {
      Object.defineProperty(global, "window", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "window", {
        configurable: true,
        value: originalWindow,
      });
    }

    if (originalDocument === undefined) {
      Object.defineProperty(global, "document", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "document", {
        configurable: true,
        value: originalDocument,
      });
    }

    if (originalSessionStorage === undefined) {
      Object.defineProperty(global, "sessionStorage", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "sessionStorage", {
        configurable: true,
        value: originalSessionStorage,
      });
    }
  });

  it("reads the CSRF token from the document cookie when available", () => {
    Object.defineProperty(global, "document", {
      configurable: true,
      value: {
        cookie: "foo=bar; csrftoken=csrf-123; theme=anct",
      },
    });

    expect(getCSRFToken()).toBe("csrf-123");
  });

  it("returns null when there is no document context", () => {
    Object.defineProperty(global, "document", {
      configurable: true,
      value: undefined,
    });

    expect(getCSRFToken()).toBeNull();
  });

  it("keeps ensureCsrfCookie single-flight while a request is already in progress", async () => {
    let resolveFetch: ((value: Response) => void) | undefined;
    (global.fetch as jest.Mock).mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const first = ensureCsrfCookie();
    const second = ensureCsrfCookie();

    expect(global.fetch).toHaveBeenCalledTimes(1);

    resolveFetch?.(new Response("{}", { status: 200 }));
    await Promise.all([first, second]);
  });

  it("builds query params and JSON headers for regular requests", async () => {
    Object.defineProperty(global, "document", {
      configurable: true,
      value: {
        cookie: "csrftoken=csrf-123",
      },
    });
    (global.fetch as jest.Mock).mockResolvedValue(
      new Response("{}", { status: 200 }),
    );

    await fetchAPI(
      "items/",
      {
        body: JSON.stringify({ title: "Doc" }),
        headers: { Accept: "application/json" },
        method: "POST",
        params: { exact: true, page: 2, q: "doc" },
      },
      { timeoutMs: 5000 },
    );

    expect(String((global.fetch as jest.Mock).mock.calls[0][0])).toBe(
      "http://api.example.test/api/v1.0/items/?exact=true&page=2&q=doc",
    );
    expect((global.fetch as jest.Mock).mock.calls[0][1]).toEqual(
      expect.objectContaining({
        credentials: "include",
        headers: expect.objectContaining({
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": "csrf-123",
        }),
        method: "POST",
      }),
    );
  });

  it("omits the JSON content-type header when the request body is FormData", async () => {
    Object.defineProperty(global, "document", {
      configurable: true,
      value: {
        cookie: "csrftoken=csrf-123",
      },
    });
    (global.fetch as jest.Mock).mockResolvedValue(
      new Response("{}", { status: 200 }),
    );

    await fetchAPI("upload/", {
      body: new FormData(),
      method: "POST",
    });

    expect((global.fetch as jest.Mock).mock.calls[0][1]).toEqual(
      expect.objectContaining({
        headers: expect.not.objectContaining({
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("maps abort errors to the translated AppError timeout message", async () => {
    (global.fetch as jest.Mock).mockRejectedValue(
      new DOMException("Timeout", "AbortError"),
    );

    await expect(fetchAPI("items/", undefined, { timeoutMs: 1 })).rejects.toBeInstanceOf(
      AppError,
    );
    await expect(fetchAPI("items/", undefined, { timeoutMs: 1 })).rejects.toMatchObject(
      {
        message: "translated:api.error.timeout",
      },
    );
  });

  it("redirects 401 responses to /401 and stores the attempted URL", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(new Response("", { status: 401 }));

    await expect(fetchAPI("items/")).rejects.toBeInstanceOf(APIError);

    expect(setItem).toHaveBeenCalledWith(
      "redirect_after_login_url",
      "http://192.168.10.123:3000/explorer/items/my-files",
    );
    expect(global.window.location.href).toBe("/401");
  });

  it("redirects 403 responses to /403 without storing the attempted URL", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(new Response("", { status: 403 }));

    await expect(fetchAPI("items/")).rejects.toBeInstanceOf(APIError);

    expect(setItem).not.toHaveBeenCalled();
    expect(global.window.location.href).toBe("/403");
  });

  it("parses JSON error payloads into APIError data", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      new Response(JSON.stringify({ detail: "boom" }), { status: 500 }),
    );

    try {
      await fetchAPI("items/");
      throw new Error("expected fetchAPI to throw");
    } catch (error) {
      expect(error).toBeInstanceOf(APIError);
      expect((error as APIError).code).toBe(500);
      expect((error as APIError).data).toEqual({ detail: "boom" });
    }
  });

  it("keeps non-JSON error payloads as generic APIError responses", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      new Response("backend exploded", { status: 500 }),
    );

    try {
      await fetchAPI("items/");
      throw new Error("expected fetchAPI to throw");
    } catch (error) {
      expect(error).toBeInstanceOf(APIError);
      expect((error as APIError).code).toBe(500);
      expect((error as APIError).data).toBeUndefined();
    }
  });
});
