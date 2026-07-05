import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { setFromRoute } from "@/features/explorer/utils/utils";
import { DefaultRoute } from "@/utils/defaultRoutes";

import { useDefaultRoute } from "../useDefaultRoute";

jest.mock("@/features/explorer/utils/utils", () => ({
  setFromRoute: jest.fn(),
}));

const mockedSetFromRoute = jest.mocked(setFromRoute);

const Probe = ({ defaultRoute }: { defaultRoute: DefaultRoute }) => {
  useDefaultRoute(defaultRoute);
  return <div>probe</div>;
};

describe("useDefaultRoute", () => {
  it("pushes the provided default route once on mount", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });

    renderToStaticMarkup(<Probe defaultRoute={DefaultRoute.MOUNTS} />);

    expect(mockedSetFromRoute).toHaveBeenCalledWith(DefaultRoute.MOUNTS);

    useEffectSpy.mockRestore();
  });
});
