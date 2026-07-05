const driverInstance = { id: "driver-1" };

jest.mock("../../drivers/implementations/StandardDriver", () => ({
  StandardDriver: jest.fn(() => driverInstance),
}));

import { StandardDriver } from "../../drivers/implementations/StandardDriver";
import { getConfig, getDriver } from "../Config";

const mockedStandardDriver = jest.mocked(StandardDriver);

describe("Config", () => {
  beforeEach(() => {
    mockedStandardDriver.mockClear();
  });

  it("uses StandardDriver as the default configured driver", () => {
    expect(getConfig()).toEqual({
      driver: driverInstance,
    });
    expect(mockedStandardDriver).toHaveBeenCalledTimes(1);
  });

  it("returns the configured driver helper directly", () => {
    expect(getDriver()).toBe(driverInstance);
    expect(mockedStandardDriver).toHaveBeenCalledTimes(1);
  });
});
