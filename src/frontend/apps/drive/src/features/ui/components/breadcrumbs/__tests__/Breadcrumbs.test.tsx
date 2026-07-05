import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  Breadcrumbs,
  type BreadcrumbItem,
} from "../Breadcrumbs";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => <button onClick={onClick}>{children}</button>,
}));

describe("Breadcrumbs", () => {
  it("wraps each breadcrumb segment in a dedicated shared host container", () => {
    const items: BreadcrumbItem[] = [
      {
        content: <button className="c__breadcrumbs__button">Root</button>,
      },
      {
        content: <button className="c__breadcrumbs__button">Long segment</button>,
      },
    ];

    const html = renderToStaticMarkup(<Breadcrumbs items={items} />);

    expect(html).toContain("data-testid=\"explorer-breadcrumbs\"");
    expect(html).toContain("c__breadcrumbs__item");
    expect(html).toContain("chevron_right");
    expect(html).toContain("c__breadcrumbs__button active");
  });
});
