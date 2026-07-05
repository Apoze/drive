export const getConstrainedImageViewerPosition = ({
  newPosition,
  containerWidth,
  containerHeight,
  naturalWidth,
  naturalHeight,
  zoom,
}: {
  newPosition: { x: number; y: number };
  containerWidth: number;
  containerHeight: number;
  naturalWidth: number;
  naturalHeight: number;
  zoom: number;
}) => {
  const scaledWidth = naturalWidth * zoom;
  const scaledHeight = naturalHeight * zoom;

  const maxX = Math.max(0, (scaledWidth - containerWidth) / 2);
  const minX = -maxX;
  const maxY = Math.max(0, (scaledHeight - containerHeight) / 2);
  const minY = -maxY;

  return {
    x: Math.max(minX, Math.min(maxX, newPosition.x)),
    y: Math.max(minY, Math.min(maxY, newPosition.y)),
  };
};
