import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { useConfig } from "@/features/config/ConfigProvider";

import { Feedback } from "../Feedback";
import { useMessagesWidget } from "../useMessagesWidget";

const renderedButtons: Array<Record<string, unknown>> = [];
const renderedModals: Array<Record<string, unknown>> = [];
const modalOpen = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: jest.fn(),
}));

jest.mock("../useMessagesWidget", () => ({
  useMessagesWidget: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: ({ name }: { name: string }) => <div>icon:{name}</div>,
  IconType: {
    OUTLINED: "outlined",
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => {
    renderedButtons.push(props as Record<string, unknown>);
    return <button>{props.children}</button>;
  },
  Modal: (props: { children?: React.ReactNode; title: string }) => {
    renderedModals.push(props as Record<string, unknown>);
    return (
      <div>
        modal:{props.title}
        {props.children}
      </div>
    );
  },
  ModalSize: {
    MEDIUM: "medium",
  },
  useModal: () => ({
    isOpen: false,
    open: modalOpen,
  }),
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedUseConfig = jest.mocked(useConfig);
const mockedUseMessagesWidget = jest.mocked(useMessagesWidget);

describe("Feedback", () => {
  const showWidget = jest.fn();

  beforeEach(() => {
    renderedButtons.length = 0;
    renderedModals.length = 0;
    modalOpen.mockClear();
    showWidget.mockClear();
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
    mockedUseMessagesWidget.mockReturnValue({
      showWidget,
    } as never);
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_FEEDBACK_BUTTON_IDLE: false,
        FRONTEND_FEEDBACK_BUTTON_SHOW: true,
        FRONTEND_FEEDBACK_ITEMS: {
          form: { url: "https://form.example.test" },
        },
        FRONTEND_FEEDBACK_MESSAGES_WIDGET_ENABLED: false,
      },
    } as never);
  });

  it("hides the feedback entrypoint when disabled by config", () => {
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_FEEDBACK_BUTTON_SHOW: false,
      },
    } as never);

    expect(renderToStaticMarkup(<Feedback />)).toBe("");
  });

  it("keeps the button visible in idle mode and does not open anything on click", () => {
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_FEEDBACK_BUTTON_IDLE: true,
        FRONTEND_FEEDBACK_BUTTON_SHOW: true,
        FRONTEND_FEEDBACK_ITEMS: {},
        FRONTEND_FEEDBACK_MESSAGES_WIDGET_ENABLED: false,
      },
    } as never);

    const html = renderToStaticMarkup(<Feedback />);

    expect(html).toContain("translated:feedback.button");
    (renderedButtons[0].onClick as () => void)();
    expect(showWidget).not.toHaveBeenCalled();
    expect(modalOpen).not.toHaveBeenCalled();
  });

  it("delegates to the messages widget when widget mode is enabled", () => {
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_FEEDBACK_BUTTON_IDLE: false,
        FRONTEND_FEEDBACK_BUTTON_SHOW: true,
        FRONTEND_FEEDBACK_ITEMS: {
          form: { url: "https://form.example.test" },
        },
        FRONTEND_FEEDBACK_MESSAGES_WIDGET_ENABLED: true,
      },
    } as never);

    renderToStaticMarkup(<Feedback />);

    (renderedButtons[0].onClick as () => void)();
    expect(showWidget).toHaveBeenCalledTimes(1);
    expect(modalOpen).not.toHaveBeenCalled();
  });

  it("opens the modal when widget mode is disabled", () => {
    const html = renderToStaticMarkup(<Feedback />);

    expect(html).toContain("translated:feedback.button");
    expect(html).toContain("modal:translated:feedback.modal.title");
    expect(html).toContain("translated:feedback.modal.buttons.form.title");
    expect(renderedModals).toHaveLength(1);

    (renderedButtons[0].onClick as () => void)();
    expect(modalOpen).toHaveBeenCalledTimes(1);
  });
});
