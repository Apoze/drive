import { getConstrainedImageViewerPosition } from "../imageViewerMath";

describe("getConstrainedImageViewerPosition", () => {
  it("clamps image dragging inside the visible bounds", () => {
    expect(
      getConstrainedImageViewerPosition({
        newPosition: { x: 500, y: -500 },
        containerWidth: 300,
        containerHeight: 200,
        naturalWidth: 400,
        naturalHeight: 300,
        zoom: 2,
      }),
    ).toEqual({
      x: 250,
      y: -200,
    });

    expect(
      getConstrainedImageViewerPosition({
        newPosition: { x: 10, y: 10 },
        containerWidth: 800,
        containerHeight: 600,
        naturalWidth: 200,
        naturalHeight: 100,
        zoom: 1,
      }),
    ).toEqual({
      x: 0,
      y: 0,
    });
  });
});
