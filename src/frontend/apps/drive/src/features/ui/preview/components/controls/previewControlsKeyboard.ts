export type PreviewControlsKeyboardHandlers = {
  togglePlay: () => void;
  rewind10Seconds: () => void;
  forward10Seconds: () => void;
};

export const handlePreviewControlsKeyDown = ({
  event,
  isFullscreen,
  togglePlay,
  rewind10Seconds,
  forward10Seconds,
}: PreviewControlsKeyboardHandlers & {
  event: Pick<KeyboardEvent, "code" | "preventDefault">;
  isFullscreen: boolean;
}) => {
  if (isFullscreen) {
    return false;
  }

  switch (event.code) {
    case "Space":
      event.preventDefault();
      togglePlay();
      return true;
    case "ArrowLeft":
      event.preventDefault();
      rewind10Seconds();
      return true;
    case "ArrowRight":
      event.preventDefault();
      forward10Seconds();
      return true;
    default:
      return false;
  }
};
