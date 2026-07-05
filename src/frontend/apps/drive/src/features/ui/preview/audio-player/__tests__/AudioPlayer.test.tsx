import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AudioPlayer } from "../AudioPlayer";

const renderedPreviewControls: Array<{
  togglePlay: () => void;
  handleVolumeChange: (newVolume: number) => void;
  toggleMute: () => void;
  rewind10Seconds: () => void;
  forward10Seconds: () => void;
}> = [];

const renderedProgressBars: Array<{
  handleSeek: (event: { target: { value: string } }) => void;
}> = [];

jest.mock("../../components/duration-bar/DurationBar", () => ({
  ProgressBar: (props: { handleSeek: (event: { target: { value: string } }) => void }) => {
    renderedProgressBars.push(props);
    return <div>progress-bar</div>;
  },
}));

jest.mock("../../components/controls/PreviewControls", () => ({
  PreviewControls: (props: {
    togglePlay: () => void;
    handleVolumeChange: (newVolume: number) => void;
    toggleMute: () => void;
    rewind10Seconds: () => void;
    forward10Seconds: () => void;
  }) => {
    renderedPreviewControls.push(props);
    return <div>preview-controls</div>;
  },
}));

describe("AudioPlayer", () => {
  let useRefSpy: jest.SpiedFunction<typeof React.useRef> | undefined;
  let useStateSpy: jest.SpiedFunction<typeof React.useState> | undefined;

  beforeEach(() => {
    renderedPreviewControls.length = 0;
    renderedProgressBars.length = 0;
  });

  afterEach(() => {
    useRefSpy?.mockRestore();
    useStateSpy?.mockRestore();
  });

  it("wires audio controls, seek and mute through the shared preview controls", () => {
    const fakeAudio = {
      play: jest.fn(),
      pause: jest.fn(),
      currentTime: 0,
      volume: 1,
    };

    useRefSpy = jest.spyOn(React, "useRef").mockReturnValue({
      current: fakeAudio,
    } as never);
    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementationOnce((() => [false, jest.fn()]) as never)
      .mockImplementationOnce((() => [20, jest.fn()]) as never)
      .mockImplementationOnce((() => [50, jest.fn()]) as never)
      .mockImplementationOnce((() => [0.6, jest.fn()]) as never)
      .mockImplementationOnce((() => [false, jest.fn()]) as never);

    const html = renderToStaticMarkup(
      <AudioPlayer src="https://example.test/audio.mp3" title="Demo audio" />,
    );

    renderedPreviewControls[0]?.togglePlay();
    renderedProgressBars[0]?.handleSeek({ target: { value: "15" } });
    renderedPreviewControls[0]?.handleVolumeChange(0.3);
    renderedPreviewControls[0]?.toggleMute();
    renderedPreviewControls[0]?.rewind10Seconds();
    renderedPreviewControls[0]?.forward10Seconds();

    expect(html).toContain("Demo audio");
    expect(html).toContain("preview-controls");
    expect(fakeAudio.play).toHaveBeenCalledTimes(1);
    expect(fakeAudio.currentTime).toBe(30);
    expect(fakeAudio.volume).toBe(0);
  });

  it("restores the previous volume when unmuting an already-muted audio player", () => {
    const fakeAudio = {
      play: jest.fn(),
      pause: jest.fn(),
      currentTime: 0,
      volume: 0,
    };

    useRefSpy = jest.spyOn(React, "useRef").mockReturnValue({
      current: fakeAudio,
    } as never);
    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementationOnce((() => [true, jest.fn()]) as never)
      .mockImplementationOnce((() => [0, jest.fn()]) as never)
      .mockImplementationOnce((() => [50, jest.fn()]) as never)
      .mockImplementationOnce((() => [0.6, jest.fn()]) as never)
      .mockImplementationOnce((() => [true, jest.fn()]) as never);

    renderToStaticMarkup(
      <AudioPlayer src="https://example.test/audio.mp3" title="Muted audio" />,
    );

    renderedPreviewControls[0]?.toggleMute();

    expect(fakeAudio.volume).toBe(0.6);
  });
});
