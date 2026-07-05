import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { useTimeBoundedPhase } from "../useTimeBoundedPhase";

const Probe = ({
  bounds,
  isActive,
}: {
  bounds: { fail_ms: number; still_working_ms: number };
  isActive: boolean;
}) => {
  const phase = useTimeBoundedPhase(isActive, bounds);
  return <div>{phase}</div>;
};

describe("useTimeBoundedPhase", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it("resets to loading and clears startedAt when the hook becomes inactive", () => {
    const setStartedAt = jest.fn();
    const setPhase = jest.fn();
    jest
      .spyOn(React, "useState")
      .mockReturnValueOnce([123, setStartedAt] as never)
      .mockReturnValueOnce(["failed", setPhase] as never);
    jest.spyOn(React, "useEffect").mockImplementation((effect) => {
      effect();
    });

    renderToStaticMarkup(
      <Probe bounds={{ fail_ms: 200, still_working_ms: 100 }} isActive={false} />,
    );

    expect(setStartedAt).toHaveBeenCalledWith(null);
    expect(setPhase).toHaveBeenCalledWith("loading");
  });

  it("moves from loading to still_working then failed once timers elapse", () => {
    const setStartedAt = jest.fn();
    const setPhase = jest.fn();
    jest.spyOn(Date, "now").mockReturnValue(1000);
    jest
      .spyOn(React, "useState")
      .mockReturnValueOnce([1000, setStartedAt] as never)
      .mockReturnValueOnce(["loading", setPhase] as never);
    jest.spyOn(React, "useEffect").mockImplementation((effect) => {
      effect();
    });

    renderToStaticMarkup(
      <Probe bounds={{ fail_ms: 200, still_working_ms: 100 }} isActive={true} />,
    );

    setPhase.mockClear();
    jest.advanceTimersByTime(100);
    expect(setPhase).toHaveBeenCalledWith("still_working");

    setPhase.mockClear();
    jest.advanceTimersByTime(100);
    expect(setPhase).toHaveBeenCalledWith("failed");
  });

  it("cleans up both timers when the timing effect is disposed", () => {
    const setStartedAt = jest.fn();
    const setPhase = jest.fn();
    const cleanups: Array<() => void> = [];
    const clearTimeoutSpy = jest.spyOn(globalThis, "clearTimeout");
    jest
      .spyOn(React, "useState")
      .mockReturnValueOnce([1000, setStartedAt] as never)
      .mockReturnValueOnce(["loading", setPhase] as never);
    jest.spyOn(React, "useEffect").mockImplementation((effect) => {
      const cleanup = effect();
      if (typeof cleanup === "function") {
        cleanups.push(cleanup);
      }
    });

    renderToStaticMarkup(
      <Probe bounds={{ fail_ms: 200, still_working_ms: 100 }} isActive={true} />,
    );

    cleanups[0]?.();

    expect(clearTimeoutSpy).toHaveBeenCalledTimes(2);
  });
});
