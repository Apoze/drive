import {
  baseApiUrl,
  errorCauses,
  getOrigin,
  isJson,
} from "../utils";

describe("api/utils", () => {
  const originalWindow = global.window;
  const originalApiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN;
  const originalApiPort = process.env.NEXT_PUBLIC_API_PORT;

  afterEach(() => {
    process.env.NEXT_PUBLIC_API_ORIGIN = originalApiOrigin;
    process.env.NEXT_PUBLIC_API_PORT = originalApiPort;

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
  });

  it("flattens response validation errors with status and optional data", async () => {
    const response = new Response(
      JSON.stringify({
        detail: "Boom",
        title: ["Missing title", "Still missing"],
      }),
      { status: 400 },
    );

    await expect(errorCauses(response, { source: "form" })).resolves.toEqual({
      cause: ["Boom", "Missing title", "Still missing"],
      data: { source: "form" },
      status: 400,
    });
  });

  it("prefers the configured API origin when present", () => {
    process.env.NEXT_PUBLIC_API_ORIGIN = "http://api.example.test";

    expect(getOrigin()).toBe("http://api.example.test");
  });

  it("returns an empty origin on the server when no API origin is configured", () => {
    process.env.NEXT_PUBLIC_API_ORIGIN = "";
    Object.defineProperty(global, "window", {
      configurable: true,
      value: undefined,
    });

    expect(getOrigin()).toBe("");
  });

  it("derives the origin from the current location and configured port", () => {
    process.env.NEXT_PUBLIC_API_ORIGIN = "";
    process.env.NEXT_PUBLIC_API_PORT = "8079";
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          href: "https://192.168.10.123:3000/explorer/items/my-files",
        },
      },
    });

    expect(getOrigin()).toBe("https://192.168.10.123:8079");
  });

  it("builds the versioned base API URL from the derived origin", () => {
    process.env.NEXT_PUBLIC_API_ORIGIN = "http://api.example.test";

    expect(baseApiUrl()).toBe("http://api.example.test/api/v1.0/");
    expect(baseApiUrl("2.1")).toBe("http://api.example.test/api/v2.1/");
  });

  it("detects valid and invalid JSON payloads", () => {
    expect(isJson('{"ok":true}')).toBe(true);
    expect(isJson("not-json")).toBe(false);
  });
});
