import React from "react";
import { EmbeddedExplorerSearchInput } from "../EmbeddedExplorerSearchInput";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: () => <div>icon</div>,
}));

describe("EmbeddedExplorerSearchInput", () => {
  it("keeps the canonical search input placeholder, value and change wiring", () => {
    const onSearch = jest.fn();

    const tree = (EmbeddedExplorerSearchInput as unknown as {
      type: (props: { onSearch: (query: string) => void; value: string }) => {
        props: {
          children: Array<{
            props?: Record<string, unknown>;
          }>;
        };
      };
    }).type({
      onSearch,
      value: "report",
    });

    const input = tree.props.children[1] as {
      props: {
        placeholder?: string;
        value?: string;
        onChange?: (event: { target: { value: string } }) => void;
      };
    };

    expect(input.props.placeholder).toBe("Search for a folder...");
    expect(input.props.value).toBe("report");

    input.props.onChange?.({
      target: {
        value: "report 2",
      },
    });

    expect(onSearch).toHaveBeenCalledWith("report 2");
  });
});
