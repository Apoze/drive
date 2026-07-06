import React from "react";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import {
  FastBackward,
  FastForward,
  Maximize,
  Pause,
  Play,
} from "@gouvfr-lasuite/ui-kit";
import { VolumeBar } from "../volume-bar/VolumeBar";
import { useEffect } from "react";
import { handlePreviewControlsKeyDown } from "./previewControlsKeyboard";
import clsx from "clsx";

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
    <div
      className={clsx("file-preview__controls", {
        "file-preview__controls--no-fullscreen-button": !showFullscreenBtn,
      })}
    >
      <Button
        variant="tertiary"
        color="neutral"
        onClick={togglePlay}
        size="small"
        icon={isPlaying ? <Pause /> : <Play />}
      />
      <VerticalSeparator />
      <Button
        variant="tertiary"
        color="neutral"
        onClick={rewind10Seconds}
        size="small"
        icon={<FastBackward />}
      />
      <Button
        variant="tertiary"
        color="neutral"
        onClick={forward10Seconds}
        size="small"
        icon={<FastForward />}
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
            size="small"
            icon={<Maximize />}
          />
        </>
      )}
    </div>
  );
};

const VerticalSeparator = () => {
  return <div className="file-preview__controls__separator" />;
};
