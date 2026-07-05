import { getRuntimeConfig, setRuntimeConfig } from "../runtimeConfig";

describe("runtimeConfig", () => {
  it("stores and returns the latest runtime config object", () => {
    setRuntimeConfig({
      FRONTEND_MORE_LINK: "https://docs.example.test/more",
    });

    expect(getRuntimeConfig()).toEqual({
      FRONTEND_MORE_LINK: "https://docs.example.test/more",
    });
  });
});
