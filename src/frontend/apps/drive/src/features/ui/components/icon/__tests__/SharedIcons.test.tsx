import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CheckIcon } from "../CheckIcon";
import { MountsIcon } from "../MountsIcon";
import { MyFilesIcon } from "../MyFilesIcon";
import { NewFolderIcon } from "../NewFolderIcon";
import { RecentIcon } from "../RecentIcon";
import { ResetZoomIcon } from "../ResetZoomIcon";
import { SharedWithMeIcon } from "../SharedWithMeIcon";
import { StarredIcon } from "../StarredIcon";
import { TrashIcon } from "../TrashIcon";
import { ZoomMinusIcon } from "../ZoomMinusIcon";
import { ZoomPlusIcon } from "../ZoomPlusIcon";

const renderedSvgProps: Array<Record<string, unknown>> = [];
const renderedUiKitIcons: Array<Record<string, unknown>> = [];

jest.mock("../Icon", () => ({
  IconSvg: (props: {
    children?: React.ReactNode;
    size?: number | string;
    className?: string;
  }) => {
    renderedSvgProps.push(props as Record<string, unknown>);
    return (
      <svg data-size={String(props.size ?? "")} className={props.className}>
        {props.children}
      </svg>
    );
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: (props: { name: string; size?: string | number }) => {
    renderedUiKitIcons.push(props as Record<string, unknown>);
    return <div>{props.name}</div>;
  },
}));

const iconCases = [
  { label: "MyFilesIcon", Component: MyFilesIcon },
  { label: "NewFolderIcon", Component: NewFolderIcon },
  { label: "RecentIcon", Component: RecentIcon },
  { label: "ResetZoomIcon", Component: ResetZoomIcon },
  { label: "SharedWithMeIcon", Component: SharedWithMeIcon },
  { label: "StarredIcon", Component: StarredIcon },
  { label: "TrashIcon", Component: TrashIcon },
  { label: "ZoomMinusIcon", Component: ZoomMinusIcon },
  { label: "ZoomPlusIcon", Component: ZoomPlusIcon },
] as const;

describe("shared SVG icon primitives", () => {
  beforeEach(() => {
    renderedSvgProps.length = 0;
    renderedUiKitIcons.length = 0;
  });

  it("keeps CheckIcon base rendering intact", () => {
    const html = renderToStaticMarkup(<CheckIcon />);

    expect(html).toContain("<svg");
    expect(html).toContain("<animate");
    expect(html).toContain('width="20"');
  });

  it.each(iconCases)(
    "keeps %s compatible with IconSvg and forwards shared props",
    ({ Component }) => {
      const html = renderToStaticMarkup(
        <Component size={32 as never} className="shared-icon" />,
      );

      expect(html).toContain("<path");
      expect(renderedSvgProps[0]).toMatchObject({
        size: 32,
        className: "shared-icon",
      });
    },
  );

  it("keeps MountsIcon wired to the ui-kit icon primitive", () => {
    const html = renderToStaticMarkup(<MountsIcon size={"small" as never} />);

    expect(html).toContain("folder_open");
    expect(renderedUiKitIcons[0]).toMatchObject({
      name: "folder_open",
      size: "small",
    });
  });
});
