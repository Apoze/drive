import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PreviewControls } from "../PreviewControls";

const renderedButtons: Array<{
  onClick?: () => void;
  icon?: React.ReactNode;
}> = [];

const renderedVolumeBars: Array<{
  volume: number;
  isMuted: boolean;
  toggleMute: () => void;
  handleVolumeChange: (newVolume: number) => void;
}> = [];

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { onClick?: () => void; icon?: React.ReactNode }) => {
    renderedButtons.push(props);
    return <button>{props.icon}</button>;
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("../../volume-bar/VolumeBar", () => ({
  VolumeBar: (props: {
    volume: number;
    isMuted: boolean;
    toggleMute: () => void;
    handleVolumeChange: (newVolume: number) => void;
  }) => {
    renderedVolumeBars.push(props);
    return <div>volume-bar</div>;
  },
}));

describe("PreviewControls", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
    renderedVolumeBars.length = 0;
  });

  it("renders the shared controls and forwards callbacks to the host handlers", () => {
    const togglePlay = jest.fn();
    const rewind10Seconds = jest.fn();
    const forward10Seconds = jest.fn();
    const toggleMute = jest.fn();
    const handleVolumeChange = jest.fn();
    const toggleFullscreen = jest.fn();

    const html = renderToStaticMarkup(
      <PreviewControls
        togglePlay={togglePlay}
        isPlaying={false}
        rewind10Seconds={rewind10Seconds}
        forward10Seconds={forward10Seconds}
        volume={0.4}
        isMuted={false}
        toggleMute={toggleMute}
        handleVolumeChange={handleVolumeChange}
        toggleFullscreen={toggleFullscreen}
        isFullscreen={false}
        showFullscreenBtn={true}
      />,
    );

    renderedButtons[0]?.onClick?.();
    renderedButtons[1]?.onClick?.();
    renderedButtons[2]?.onClick?.();
    renderedButtons[3]?.onClick?.();
    renderedVolumeBars[0]?.toggleMute();
    renderedVolumeBars[0]?.handleVolumeChange(0.7);

    expect(html).toContain("play_arrow");
    expect(html).toContain("fullscreen");
    expect(togglePlay).toHaveBeenCalledTimes(1);
    expect(rewind10Seconds).toHaveBeenCalledTimes(1);
    expect(forward10Seconds).toHaveBeenCalledTimes(1);
    expect(toggleFullscreen).toHaveBeenCalledTimes(1);
    expect(toggleMute).toHaveBeenCalledTimes(1);
    expect(handleVolumeChange).toHaveBeenCalledWith(0.7);
    expect(renderedVolumeBars[0]).toMatchObject({
      volume: 0.4,
      isMuted: false,
    });
  });

  it("keeps the fullscreen button optional", () => {
    const html = renderToStaticMarkup(
      <PreviewControls
        togglePlay={jest.fn()}
        isPlaying={true}
        rewind10Seconds={jest.fn()}
        forward10Seconds={jest.fn()}
        volume={1}
        isMuted={false}
        toggleMute={jest.fn()}
        handleVolumeChange={jest.fn()}
        toggleFullscreen={jest.fn()}
        isFullscreen={false}
      />,
    );

    expect(renderedButtons).toHaveLength(3);
    expect(html).toContain("pause");
    expect(html).not.toContain("fullscreen");
  });
});
