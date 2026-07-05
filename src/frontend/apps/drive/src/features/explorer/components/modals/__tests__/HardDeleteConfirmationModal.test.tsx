import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { HardDeleteConfirmationModal } from "../HardDeleteConfirmationModal";

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => <button onClick={onClick}>{children}</button>,
  Modal: ({
    children,
    title,
    rightActions,
  }: {
    children?: React.ReactNode;
    title?: React.ReactNode;
    rightActions?: React.ReactNode;
  }) => (
    <div>
      <div>{title}</div>
      <div>{children}</div>
      <div>{rightActions}</div>
    </div>
  ),
  ModalSize: {
    MEDIUM: "medium",
  },
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, values?: Record<string, unknown>) => {
      if (key === "explorer.trash.hard_delete.content") {
        const count = values?.count as number | undefined;
        return count === 1
          ? "hard_delete_content_one"
          : `hard_delete_content_other_${count}`;
      }
      return key;
    },
  }),
}));

describe("HardDeleteConfirmationModal", () => {
  const baseProps = {
    isOpen: true,
    onClose: jest.fn(),
    onDecide: jest.fn(),
  };

  it.each([
    [1, "hard_delete_content_one"],
    [2, "hard_delete_content_other_2"],
    [3, "hard_delete_content_other_3"],
  ])("renders the confirmation text with the real count %s", (count, expected) => {
    const html = renderToStaticMarkup(
      <HardDeleteConfirmationModal {...baseProps} count={count} />,
    );

    expect(html).toContain(expected);
  });
});
