import { attemptSilentLogin, canAttemptSilentLogin } from "../silentLogin";

jest.mock("../authUrl", () => ({
  authUrl: jest.fn(() => ({
    href: "http://auth.example.test/authenticate/?silent=true",
  })),
}));

describe("silentLogin", () => {
  const originalWindow = global.window;
  const getItem = jest.fn();
  const setItem = jest.fn();

  beforeEach(() => {
    getItem.mockReset();
    setItem.mockReset();
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          href: "http://192.168.10.123:3000/current",
        },
      },
    });
    Object.defineProperty(global, "localStorage", {
      configurable: true,
      value: {
        getItem,
        setItem,
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

  it("allows retry when no silent-login retry is stored", () => {
    getItem.mockReturnValue(null);

    expect(canAttemptSilentLogin()).toBe(true);
  });

  it("blocks retry when the stored retry time is still in the future", () => {
    jest.spyOn(Date.prototype, "getTime").mockReturnValue(1000);
    getItem.mockReturnValue("2000");

    expect(canAttemptSilentLogin()).toBe(false);

    jest.restoreAllMocks();
  });

  it("stores the next retry time and redirects when retry is allowed", () => {
    jest.spyOn(Date.prototype, "getTime").mockReturnValue(1000);
    getItem.mockReturnValue(null);

    attemptSilentLogin(30);

    expect(setItem).toHaveBeenCalledWith("silent-login-retry", "31000");
    expect(global.window.location.href).toBe(
      "http://auth.example.test/authenticate/?silent=true",
    );

    jest.restoreAllMocks();
  });

  it("does nothing when retry is not allowed", () => {
    jest.spyOn(Date.prototype, "getTime").mockReturnValue(1000);
    getItem.mockReturnValue("2000");

    attemptSilentLogin(30);

    expect(setItem).not.toHaveBeenCalled();
    expect(global.window.location.href).toBe(
      "http://192.168.10.123:3000/current",
    );

    jest.restoreAllMocks();
  });
});
