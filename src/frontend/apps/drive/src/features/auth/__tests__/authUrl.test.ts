import { baseApiUrl } from "@/features/api/utils";

import { authUrl } from "../authUrl";

jest.mock("@/features/api/utils", () => ({
  baseApiUrl: jest.fn(() => "http://api.example.test/api/v1.0/"),
}));

const mockedBaseApiUrl = jest.mocked(baseApiUrl);

describe("authUrl", () => {
  const originalWindow = global.window;

  beforeEach(() => {
    mockedBaseApiUrl.mockReturnValue("http://api.example.test/api/v1.0/");
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          href: "http://192.168.10.123:3000/explorer/items/files",
        },
      },
    });
  });

  afterEach(() => {
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

  it("builds the default auth URL from the current location", () => {
    expect(authUrl().toString()).toBe(
      "http://api.example.test/api/v1.0/authenticate/?silent=false&returnTo=http%3A%2F%2F192.168.10.123%3A3000%2Fexplorer%2Fitems%2Ffiles",
    );
  });

  it("supports explicit silent and returnTo parameters", () => {
    expect(
      authUrl({
        returnTo: "https://return.example.test/after-login",
        silent: true,
      }).toString(),
    ).toBe(
      "http://api.example.test/api/v1.0/authenticate/?silent=true&returnTo=https%3A%2F%2Freturn.example.test%2Fafter-login",
    );
  });
});
