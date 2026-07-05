import React from "react";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { Icon } from "@gouvfr-lasuite/ui-kit";
import { VolumeBar } from "../volume-bar/VolumeBar";
import { useEffect } from "react";
import { handlePreviewControlsKeyDown } from "./previewControlsKeyboard";

export type PreviewControlsProps = {
  togglePlay: () => void;
  isPlaying: boolean;
  rewind10Seconds: () => void;
  forward10Seconds: () => void;
  volume: number;
  isMuted: boolean;
  toggleMute: () => void;
  handleVolumeChange: (newVolume: number) => void;
  toggleFullscreen: () => void;
  isFullscreen: boolean;
  showFullscreenBtn?: boolean;
};

export const PreviewControls = ({
  togglePlay,
  isPlaying,
  rewind10Seconds,
  forward10Seconds,
  volume,
  isMuted,
  toggleMute,
  handleVolumeChange,
  toggleFullscreen,
  isFullscreen,
  showFullscreenBtn = false,
}: PreviewControlsProps) => {
  // Keyboard controls
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      handlePreviewControlsKeyDown({
        event,
        isFullscreen,
        togglePlay,
        rewind10Seconds,
        forward10Seconds,
      });
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [forward10Seconds, isFullscreen, rewind10Seconds, togglePlay]);
  return (
    <div className="suite-preview-controls">
      <Button
        variant="tertiary"
        color="neutral"
        onClick={togglePlay}
        className="suite-preview-controls__btn"
        icon={<Icon name={isPlaying ? "pause" : "play_arrow"} />}
      />
      <VerticalSeparator />
      <Button
        variant="tertiary"
        color="neutral"
        onClick={rewind10Seconds}
        className="suite-preview-controls__btn"
        icon={<Icon name={"replay_10"} />}
      />
      <Button
        variant="tertiary"
        color="neutral"
        onClick={forward10Seconds}
        className="suite-preview-controls__btn"
        icon={<Icon name={"forward_10"} />}
      />
      <VerticalSeparator />

      <VolumeBar
        volume={volume}
        isMuted={isMuted}
        toggleMute={toggleMute}
        handleVolumeChange={handleVolumeChange}
      />

      {showFullscreenBtn && (
        <>
          <VerticalSeparator />

          <Button
            variant="tertiary"
            color="neutral"
            onClick={toggleFullscreen}
            className="suite-preview-controls__btn"
            icon={
              <Icon name={isFullscreen ? "fullscreen_exit" : "fullscreen"} />
            }
          />
        </>
      )}
    </div>
  );
};

const VerticalSeparator = () => {
  return <div className="controls-vertical-separator" />;
};
