import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { VideoPlayer } from "../VideoPlayer";

const renderedPreviewControls: Array<{
  togglePlay: () => void | Promise<void>;
  handleVolumeChange: (newVolume: number) => void;
  toggleMute: () => void;
  toggleFullscreen: () => void;
}> = [];

const renderedProgressBars: Array<{
  handleSeek: (event: { target: { value: string } }) => void;
}> = [];

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("../../components/duration-bar/DurationBar", () => ({
  ProgressBar: (props: { handleSeek: (event: { target: { value: string } }) => void }) => {
    renderedProgressBars.push(props);
    return <div>progress-bar</div>;
  },
}));

jest.mock("../../components/controls/PreviewControls", () => ({
  PreviewControls: (props: {
    togglePlay: () => void | Promise<void>;
    handleVolumeChange: (newVolume: number) => void;
    toggleMute: () => void;
    toggleFullscreen: () => void;
  }) => {
    renderedPreviewControls.push(props);
    return <div>preview-controls</div>;
  },
}));

describe("VideoPlayer", () => {
  let useRefSpy: jest.SpiedFunction<typeof React.useRef> | undefined;
  let useStateSpy: jest.SpiedFunction<typeof React.useState> | undefined;

  beforeEach(() => {
    renderedPreviewControls.length = 0;
    renderedProgressBars.length = 0;
  });

  afterEach(() => {
    useRefSpy?.mockRestore();
    useStateSpy?.mockRestore();
    Reflect.deleteProperty(globalThis, "document");
  });

  it("wires the generic controls to the underlying video element", async () => {
    const fakeVideo = {
      play: jest.fn().mockResolvedValue(undefined),
      pause: jest.fn(),
      volume: 1,
      muted: false,
      currentTime: 0,
      duration: 120,
      controls: false,
      requestFullscreen: jest.fn(),
      readyState: 4,
      paused: true,
    };

    Object.defineProperty(globalThis, "document", {
      value: {},
      configurable: true,
      writable: true,
    });

    useRefSpy = jest.spyOn(React, "useRef").mockReturnValue({
      current: fakeVideo,
    } as never);

    const html = renderToStaticMarkup(
      <VideoPlayer src="https://example.test/video.mp4" controls={true} />,
    );

    await renderedPreviewControls[0]?.togglePlay();
    renderedProgressBars[0]?.handleSeek({ target: { value: "15" } });
    renderedPreviewControls[0]?.handleVolumeChange(0.2);
    renderedPreviewControls[0]?.toggleMute();
    renderedPreviewControls[0]?.toggleFullscreen();

    expect(html).toContain("preview-controls");
    expect(fakeVideo.play).toHaveBeenCalledTimes(1);
    expect(fakeVideo.currentTime).toBe(15);
    expect(fakeVideo.volume).toBe(0.2);
    expect(fakeVideo.muted).toBe(true);
    expect(fakeVideo.controls).toBe(true);
    expect(fakeVideo.requestFullscreen).toHaveBeenCalledTimes(1);
  });
});
