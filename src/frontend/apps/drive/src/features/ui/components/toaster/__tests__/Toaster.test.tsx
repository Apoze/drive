import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { toast } from "react-toastify";

import { Toaster, ToasterItem, addToast } from "../Toaster";

const renderedButtons: Array<Record<string, unknown>> = [];

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    onClick?: () => void;
    variant?: string;
    size?: string;
    icon?: React.ReactNode;
  }) => {
    renderedButtons.push(props as Record<string, unknown>);
    return <button>{props.icon}close-button</button>;
  },
}));

jest.mock("react-toastify", () => ({
  ToastContainer: () => <div>toast-container</div>,
  toast: jest.fn(() => "toast-id"),
}));

const mockedToast = jest.mocked(toast);

describe("Toaster", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
    mockedToast.mockClear();
  });

  it("renders the shared toast container", () => {
    const html = renderToStaticMarkup(<Toaster />);

    expect(html).toContain("toast-container");
  });

  it("renders toaster items with the right classes and forwards close/drop", () => {
    const closeToast = jest.fn();
    const onDrop = jest.fn();

    const element = ToasterItem({
      children: "toast-content",
      className: "extra-class",
      closeButton: true,
      closeToast,
      onDrop,
      type: "error",
    });
    const html = renderToStaticMarkup(element);

    expect(html).toContain("suite__toaster__item--error");
    expect(html).toContain("extra-class");
    expect(html).toContain("toast-content");
    expect(renderedButtons).toHaveLength(1);
    expect(renderedButtons[0]).toEqual(
      expect.objectContaining({
        size: "small",
        variant: "tertiary",
      }),
    );

    const dropEvent = { type: "drop" } as React.DragEvent<HTMLDivElement>;
    (element.props as { onDrop: (event: React.DragEvent<HTMLDivElement>) => void }).onDrop(
      dropEvent,
    );
    (renderedButtons[0].onClick as () => void)();

    expect(onDrop).toHaveBeenCalledWith(dropEvent);
    expect(closeToast).toHaveBeenCalledTimes(1);
  });

  it("applies default toast options while allowing overrides", () => {
    const result = addToast(<div>toast-message</div>, {
      autoClose: 1200,
      position: "top-right",
    });

    expect(result).toBe("toast-id");
    expect(mockedToast).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        autoClose: 1200,
        className: "suite__toaster__wrapper",
        closeButton: false,
        hideProgressBar: true,
        position: "top-right",
      }),
    );
  });
});
