import { handlePreviewControlsKeyDown } from "../previewControlsKeyboard";

describe("handlePreviewControlsKeyDown", () => {
  it("routes keyboard shortcuts to the expected preview control callbacks", () => {
    const togglePlay = jest.fn();
    const rewind10Seconds = jest.fn();
    const forward10Seconds = jest.fn();
    const preventDefault = jest.fn();

    expect(
      handlePreviewControlsKeyDown({
        event: { code: "Space", preventDefault },
        isFullscreen: false,
        togglePlay,
        rewind10Seconds,
        forward10Seconds,
      }),
    ).toBe(true);
    expect(togglePlay).toHaveBeenCalledTimes(1);

    expect(
      handlePreviewControlsKeyDown({
        event: { code: "ArrowLeft", preventDefault },
        isFullscreen: false,
        togglePlay,
        rewind10Seconds,
        forward10Seconds,
      }),
    ).toBe(true);
    expect(rewind10Seconds).toHaveBeenCalledTimes(1);

    expect(
      handlePreviewControlsKeyDown({
        event: { code: "ArrowRight", preventDefault },
        isFullscreen: false,
        togglePlay,
        rewind10Seconds,
        forward10Seconds,
      }),
    ).toBe(true);
    expect(forward10Seconds).toHaveBeenCalledTimes(1);
    expect(preventDefault).toHaveBeenCalledTimes(3);
  });

  it("ignores shortcuts while fullscreen or for unrelated keys", () => {
    const togglePlay = jest.fn();
    const rewind10Seconds = jest.fn();
    const forward10Seconds = jest.fn();
    const preventDefault = jest.fn();

    expect(
      handlePreviewControlsKeyDown({
        event: { code: "Space", preventDefault },
        isFullscreen: true,
        togglePlay,
        rewind10Seconds,
        forward10Seconds,
      }),
    ).toBe(false);

    expect(
      handlePreviewControlsKeyDown({
        event: { code: "KeyK", preventDefault },
        isFullscreen: false,
        togglePlay,
        rewind10Seconds,
        forward10Seconds,
      }),
    ).toBe(false);

    expect(togglePlay).not.toHaveBeenCalled();
    expect(rewind10Seconds).not.toHaveBeenCalled();
    expect(forward10Seconds).not.toHaveBeenCalled();
    expect(preventDefault).not.toHaveBeenCalled();
  });
});
