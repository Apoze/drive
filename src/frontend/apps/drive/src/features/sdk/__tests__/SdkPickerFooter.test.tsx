import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { getDriver } from "@/features/config/Config";
import { LinkReach } from "@/features/drivers/types";

import { ClientMessageType, SDKRelayManager } from "../SdkRelayManager";
import { PickerFooter } from "../SdkPickerFooter";

const renderedButtons: Array<Record<string, unknown>> = [];
const beforeUnloadHandlers: Array<() => void | Promise<void>> = [];

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("../SdkRelayManager", () => ({
  ClientMessageType: {
    CANCEL: "CANCEL",
    ITEMS_SELECTED: "ITEMS_SELECTED",
  },
  SDKRelayManager: {
    registerEvent: jest.fn(async () => undefined),
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    disabled?: boolean;
    onClick?: () => Promise<void> | void;
  }) => {
    renderedButtons.push(props as Record<string, unknown>);
    return <button>{props.children}</button>;
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Spinner: ({ size }: { size: string }) => <div>spinner:{size}</div>,
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedGetDriver = jest.mocked(getDriver);
const mockedRegisterEvent = jest.mocked(SDKRelayManager.registerEvent);

describe("SdkPickerFooter", () => {
  const updateItem = jest.fn();
  const originalWindow = global.window;

  beforeEach(() => {
    renderedButtons.length = 0;
    beforeUnloadHandlers.length = 0;
    updateItem.mockReset();
    mockedRegisterEvent.mockReset();
    mockedUseTranslation.mockReturnValue({
      t: (key: string, params?: Record<string, unknown>) =>
        params && "count" in params
          ? `translated:${key}:${params.count}`
          : `translated:${key}`,
    } as never);
    mockedGetDriver.mockReturnValue({
      updateItem,
    } as never);
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        addEventListener: jest.fn(
          (_event: string, handler: () => void | Promise<void>) => {
            beforeUnloadHandlers.push(handler);
          },
        ),
        close: jest.fn(),
      },
    });
  });

  afterEach(() => {
    if (originalWindow === undefined) {
      Object.defineProperty(global, "window", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "window", {
        configurable: true,
        value: originalWindow,
      });
    }
  });

  it("renders the footer caption and action buttons", () => {
    const html = renderToStaticMarkup(
      <PickerFooter token="sdk-token" selectedItems={[]} />,
    );

    expect(html).toContain("translated:sdk.explorer.picker_label:0");
    expect(html).toContain("translated:sdk.explorer.cancel");
    expect(html).toContain("translated:sdk.explorer.choose");
    expect(renderedButtons[1]).toEqual(
      expect.objectContaining({
        disabled: true,
      }),
    );
  });

  it("upgrades non-public items and emits ITEMS_SELECTED on choose", async () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    updateItem.mockResolvedValue(undefined);

    renderToStaticMarkup(
      <PickerFooter
        token="sdk-token"
        selectedItems={[
          { id: "file-1", link_reach: LinkReach.RESTRICTED } as never,
          { id: "file-2", link_reach: LinkReach.PUBLIC } as never,
        ]}
      />,
    );

    await (renderedButtons[1].onClick as () => Promise<void>)();

    expect(updateItem).toHaveBeenCalledTimes(1);
    expect(updateItem).toHaveBeenCalledWith({
      id: "file-1",
      link_reach: LinkReach.PUBLIC,
      link_role: "reader",
    });
    expect(mockedRegisterEvent).toHaveBeenCalledWith("sdk-token", {
      data: {
        items: [
          { id: "file-1", link_reach: LinkReach.RESTRICTED },
          { id: "file-2", link_reach: LinkReach.PUBLIC },
        ],
      },
      type: ClientMessageType.ITEMS_SELECTED,
    });
    expect(global.window.close).toHaveBeenCalledTimes(1);

    await beforeUnloadHandlers[0]?.();
    expect(mockedRegisterEvent).toHaveBeenCalledTimes(1);

    useEffectSpy.mockRestore();
  });

  it("emits CANCEL on explicit cancel and on beforeunload when nothing was chosen", async () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });

    renderToStaticMarkup(
      <PickerFooter token="sdk-token" selectedItems={[{ id: "file-1" } as never]} />,
    );

    await (renderedButtons[0].onClick as () => Promise<void>)();
    await beforeUnloadHandlers[0]?.();

    expect(mockedRegisterEvent).toHaveBeenNthCalledWith(1, "sdk-token", {
      data: {},
      type: ClientMessageType.CANCEL,
    });
    expect(mockedRegisterEvent).toHaveBeenNthCalledWith(2, "sdk-token", {
      data: {},
      type: ClientMessageType.CANCEL,
    });

    useEffectSpy.mockRestore();
  });
});
