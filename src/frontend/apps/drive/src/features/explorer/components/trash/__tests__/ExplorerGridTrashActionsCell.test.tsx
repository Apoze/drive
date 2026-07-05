import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { BatchOperationError } from "@/features/errors/BatchOperationError";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import {
  useMutationHardDeleteItems,
  useMutationRestoreItems,
} from "@/features/explorer/hooks/useMutations";
import { EmbeddedExplorerGridActionsCellProps } from "../../embedded-explorer/EmbeddedExplorerGridActionsCell";
import { ExplorerGridTrashActionsCell } from "../ExplorerGridTrashActionsCell";

const renderedDropdownProps: Array<{
  options?: Array<{ label?: string; callback?: () => void }>;
  isOpen?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
}> = [];
const renderedButtonProps: Array<{
  onClick?: () => void;
}> = [];
const renderedModalProps: Array<{
  onDecide?: (decision: "yes" | null) => Promise<void> | void;
  count?: number;
}> = [];

const modalState = {
  isOpen: false,
  open: jest.fn(),
  close: jest.fn(),
};

const mockRestoreMutateAsync = jest.fn();
const mockHardDeleteMutateAsync = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  DropdownMenu: (props: {
    children?: React.ReactNode;
    options?: Array<{ label?: string; callback?: () => void }>;
    isOpen?: boolean;
    onOpenChange?: (isOpen: boolean) => void;
  }) => {
    renderedDropdownProps.push(props);
    return <div>{props.children}</div>;
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { onClick?: () => void }) => {
    renderedButtonProps.push(props);
    return <button />;
  },
  useModal: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/features/explorer/hooks/useMutations", () => ({
  useMutationRestoreItems: jest.fn(),
  useMutationHardDeleteItems: jest.fn(),
}));

jest.mock(
  "@/features/explorer/components/modals/HardDeleteConfirmationModal",
  () => ({
    HardDeleteConfirmationModal: (props: {
      onDecide?: (decision: "yes" | null) => Promise<void> | void;
      count?: number;
    }) => {
      renderedModalProps.push(props);
      return <div>hard-delete-modal</div>;
    },
  }),
);

const mockedUseModal = jest.mocked(useModal);
const mockedAddToast = jest.mocked(addToast);
const mockedUseMutationRestoreItems = jest.mocked(useMutationRestoreItems);
const mockedUseMutationHardDeleteItems = jest.mocked(useMutationHardDeleteItems);

const buildItem = () =>
  ({
    id: "trash-item-1",
    title: "Deleted report",
  }) as never;

describe("ExplorerGridTrashActionsCell", () => {
  let useStateSpy: jest.SpiedFunction<typeof React.useState> | undefined;

  beforeEach(() => {
    renderedDropdownProps.length = 0;
    renderedButtonProps.length = 0;
    renderedModalProps.length = 0;
    modalState.isOpen = false;
    modalState.open.mockReset();
    modalState.close.mockReset();
    mockedAddToast.mockReset();
    mockRestoreMutateAsync.mockReset();
    mockHardDeleteMutateAsync.mockReset();
    mockedUseModal.mockImplementation(
      () =>
        ({
          isOpen: modalState.isOpen,
          open: () => {
            modalState.isOpen = true;
            modalState.open();
          },
          close: () => {
            modalState.isOpen = false;
            modalState.close();
          },
        }) as never,
    );
    mockedUseMutationRestoreItems.mockReturnValue({
      mutateAsync: mockRestoreMutateAsync,
    } as never);
    mockedUseMutationHardDeleteItems.mockReturnValue({
      mutateAsync: mockHardDeleteMutateAsync,
    } as never);
  });

  afterEach(() => {
    useStateSpy?.mockRestore();
  });

  it("wires the dropdown toggle and restore action", async () => {
    const setIsOpen = jest.fn();
    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementationOnce((() => [false, setIsOpen]) as never);
    const params = {
      row: { original: buildItem() },
    } as unknown as EmbeddedExplorerGridActionsCellProps;

    renderToStaticMarkup(
      <ExplorerGridTrashActionsCell {...params} />,
    );

    renderedButtonProps[0]?.onClick?.();
    await renderedDropdownProps[0]?.options?.[0]?.callback?.();

    expect(setIsOpen).toHaveBeenCalledWith(true);
    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(mockRestoreMutateAsync).toHaveBeenCalledWith(["trash-item-1"]);
  });

  it("opens the hard-delete confirmation modal from the dropdown action", () => {
    const params = {
      row: { original: buildItem() },
    } as unknown as EmbeddedExplorerGridActionsCellProps;

    renderToStaticMarkup(
      <ExplorerGridTrashActionsCell {...params} />,
    );

    renderedDropdownProps[0]?.options?.[1]?.callback?.();

    expect(modalState.open).toHaveBeenCalledTimes(1);
  });

  it("runs hard delete only on positive confirmation", async () => {
    modalState.isOpen = true;
    const params = {
      row: { original: buildItem() },
    } as unknown as EmbeddedExplorerGridActionsCellProps;

    renderToStaticMarkup(
      <ExplorerGridTrashActionsCell {...params} />,
    );

    await renderedModalProps[0]?.onDecide?.(null);
    expect(mockHardDeleteMutateAsync).not.toHaveBeenCalled();

    await renderedModalProps[0]?.onDecide?.("yes");

    expect(renderedModalProps[0]?.count).toBe(1);
    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(mockHardDeleteMutateAsync).toHaveBeenCalledWith(["trash-item-1"]);
  });

  it("keeps restore failures local without sending a premature success toast", async () => {
    mockRestoreMutateAsync.mockRejectedValue(
      new BatchOperationError({
        completedIds: [],
        failedId: "trash-item-1",
        cause: new Error("403"),
      }),
    );
    const params = {
      row: { original: buildItem() },
    } as unknown as EmbeddedExplorerGridActionsCellProps;

    renderToStaticMarkup(
      <ExplorerGridTrashActionsCell {...params} />,
    );

    await renderedDropdownProps[0]?.options?.[0]?.callback?.();

    expect(mockRestoreMutateAsync).toHaveBeenCalledWith(["trash-item-1"]);
    expect(mockedAddToast).toHaveBeenCalledTimes(1);
  });
});
