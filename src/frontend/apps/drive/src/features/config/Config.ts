import { StandardDriver } from "../drivers/implementations/StandardDriver";

export const getConfig = () => {
  // TODO: Later, be based on URL query params for instance.
  return {
    driver: new StandardDriver(),
  };
};

export const getDriver = () => {
  return getConfig().driver;
};
