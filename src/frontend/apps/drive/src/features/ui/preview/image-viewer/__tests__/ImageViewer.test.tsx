import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ImageViewer } from "../ImageViewer";

const renderedButtons: Array<{
  onClick?: () => void;
}> = [];

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { onClick?: () => void; children?: React.ReactNode }) => {
    renderedButtons.push(props);
    return <button>{props.children}</button>;
  },
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("../../../components/icon/ResetZoomIcon", () => ({
  ResetZoomIcon: () => <span>reset-icon</span>,
}));

jest.mock("../../../components/icon/ZoomMinusIcon", () => ({
  ZoomMinusIcon: () => <span>zoom-out-icon</span>,
}));

jest.mock("../../../components/icon/ZoomPlusIcon", () => ({
  ZoomPlusIcon: () => <span>zoom-in-icon</span>,
}));

describe("ImageViewer", () => {
  let useStateSpy: jest.SpiedFunction<typeof React.useState> | undefined;

  beforeEach(() => {
    renderedButtons.length = 0;
  });

  afterEach(() => {
    useStateSpy?.mockRestore();
  });

  it("renders the loaded image state and keeps zoom/reset controls wired", () => {
    const setZoom = jest.fn();
    const setPosition = jest.fn();
    const setIsDragging = jest.fn();
    const setDragStart = jest.fn();
    const setImageLoaded = jest.fn();
    const setImageDimensions = jest.fn();
    const setTouchStart = jest.fn();
    const setTouchDistance = jest.fn();
    const setInitialZoomOnTouch = jest.fn();

    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementationOnce((() => [2, setZoom]) as never)
      .mockImplementationOnce((() => [{ x: 10, y: 20 }, setPosition]) as never)
      .mockImplementationOnce((() => [false, setIsDragging]) as never)
      .mockImplementationOnce((() => [{ x: 0, y: 0 }, setDragStart]) as never)
      .mockImplementationOnce((() => [true, setImageLoaded]) as never)
      .mockImplementationOnce(
        (() => [
          {
            width: 500,
            height: 400,
            naturalWidth: 1000,
            naturalHeight: 800,
            originalZoom: 1,
          },
          setImageDimensions,
        ]) as never,
      )
      .mockImplementationOnce((() => [null, setTouchStart]) as never)
      .mockImplementationOnce((() => [null, setTouchDistance]) as never)
      .mockImplementationOnce((() => [1, setInitialZoomOnTouch]) as never);

    const html = renderToStaticMarkup(
      <ImageViewer src="https://example.test/image.png" alt="demo" />,
    );

    renderedButtons[0]?.onClick?.();
    renderedButtons[1]?.onClick?.();
    renderedButtons[2]?.onClick?.();

    const zoomOutUpdater = setZoom.mock.calls[0]?.[0] as
      | ((prevZoom: number) => number)
      | undefined;
    const zoomInUpdater = setZoom.mock.calls[2]?.[0] as
      | ((prevZoom: number) => number)
      | undefined;

    expect(html).toContain("translate(10px, 20px) scale(2)");
    expect(html).toContain("src=\"https://example.test/image.png\"");
    expect(html).toContain("alt=\"demo\"");
    expect(zoomOutUpdater?.(2)).toBe(1.75);
    expect(setZoom).toHaveBeenNthCalledWith(2, 1);
    expect(setPosition).toHaveBeenCalledWith({ x: 0, y: 0 });
    expect(zoomInUpdater?.(2)).toBe(2.25);
  });
});
