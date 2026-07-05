import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { ExplorerSearchButton } from "../ExplorerSearchButton";

const renderedButtonProps: Array<{
  ["aria-label"]?: string;
  onClick?: () => void;
}> = [];
const renderedModalProps: Array<{
  defaultFilters?: Record<string, string>;
  isOpen?: boolean;
}> = [];
const mockDocumentAddEventListener = jest.fn();
const mockDocumentRemoveEventListener = jest.fn();

jest.mock("react", () => {
  const actual = jest.requireActual("react");

  return {
    ...actual,
    useEffect: jest.fn((callback: () => void | (() => void)) => {
      callback();
    }),
  };
});

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { ["aria-label"]?: string; onClick?: () => void }) => {
    renderedButtonProps.push(props);
    return <button />;
  },
  useModal: jest.fn(),
}));

jest.mock(
  "@/features/explorer/components/modals/search/ExplorerSearchModal",
  () => ({
    ExplorerSearchModal: (props: {
      defaultFilters?: Record<string, string>;
      isOpen?: boolean;
    }) => {
      renderedModalProps.push(props);
      return <div>search-modal</div>;
    },
  }),
);

const mockedUseModal = jest.mocked(useModal);

describe("ExplorerSearchButton", () => {
  beforeEach(() => {
    renderedButtonProps.length = 0;
    renderedModalProps.length = 0;
    mockDocumentAddEventListener.mockReset();
    mockDocumentRemoveEventListener.mockReset();
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: {
        addEventListener: mockDocumentAddEventListener,
        removeEventListener: mockDocumentRemoveEventListener,
      },
    });
  });

  it("keeps the canonical modal host wired through the button", () => {
    const searchModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };

    mockedUseModal.mockReturnValue(searchModal as never);

    renderToStaticMarkup(
      <ExplorerSearchButton
        defaultFilters={{ workspace: "workspace-1" }}
      />,
    );

    renderedButtonProps[0]?.onClick?.();

    expect(renderedModalProps).toEqual([
      expect.objectContaining({
        defaultFilters: {
          workspace: "workspace-1",
        },
        isOpen: false,
      }),
    ]);
    expect(renderedButtonProps[0]?.["aria-label"]).toBe(
      "explorer.tree.search",
    );
    expect(searchModal.open).toHaveBeenCalled();
  });

  it("registers the keyboard shortcut only when requested", () => {
    const searchModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };

    mockedUseModal.mockReturnValue(searchModal as never);

    renderToStaticMarkup(<ExplorerSearchButton keyboardShortcut />);

    const keydownHandler = mockDocumentAddEventListener.mock.calls.find(
      ([eventName]) => eventName === "keydown",
    )?.[1] as
      | ((event: {
          key: string;
          metaKey?: boolean;
          ctrlKey?: boolean;
          preventDefault: () => void;
        }) => void)
      | undefined;

    expect(keydownHandler).toBeDefined();

    const preventDefault = jest.fn();
    keydownHandler?.({
      key: "k",
      ctrlKey: true,
      preventDefault,
    });
    keydownHandler?.({
      key: "p",
      ctrlKey: true,
      preventDefault,
    });

    expect(preventDefault).toHaveBeenCalledTimes(1);
    expect(searchModal.open).toHaveBeenCalledTimes(1);
  });
});
