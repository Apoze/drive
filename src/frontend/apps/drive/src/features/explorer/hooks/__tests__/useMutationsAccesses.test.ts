import { Role } from "@/features/drivers/types";
import {
  useMutationCreateAccess,
  useMutationCreateInvitation,
  useMutationDeleteAccess,
  useMutationDeleteInvitation,
  useMutationUpdateAccess,
  useMutationUpdateInvitation,
} from "../useMutationsAccesses";
import { getDriver } from "@/features/config/Config";
import { useMutation } from "@tanstack/react-query";
import { useOnSuccessAccessOrInvitationMutation } from "../useRefreshItems";

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@tanstack/react-query", () => ({
  useMutation: jest.fn((config) => config),
}));

jest.mock("../useRefreshItems", () => ({
  useOnSuccessAccessOrInvitationMutation: jest.fn(),
}));

const mockedGetDriver = jest.mocked(getDriver);
const mockedUseMutation = jest.mocked(useMutation);
const mockedUseOnSuccessAccessOrInvitationMutation = jest.mocked(
  useOnSuccessAccessOrInvitationMutation,
);

const driver = {
  createAccess: jest.fn(),
  createInvitation: jest.fn(),
  updateInvitation: jest.fn(),
  updateAccess: jest.fn(),
  deleteAccess: jest.fn(),
  deleteInvitation: jest.fn(),
};

type MutationHookConfig<T> = {
  mutationFn: (variables: T) => Promise<unknown>;
  onSuccess: (data: unknown, variables: T) => void;
};

type CapturedHooks = {
  createAccess: MutationHookConfig<{
    itemId: string;
    userId: string;
    role: Role;
  }>;
  createInvitation: MutationHookConfig<{
    itemId: string;
    email: string;
    role: Role;
  }>;
  updateInvitation: MutationHookConfig<{
    itemId: string;
    invitationId: string;
    role: Role;
  }>;
  updateAccess: MutationHookConfig<{
    itemId: string;
    accessId: string;
    user_id: string;
    role: Role;
  }>;
  deleteAccess: MutationHookConfig<{
    itemId: string;
    accessId: string;
  }>;
  deleteInvitation: MutationHookConfig<{
    itemId: string;
    invitationId: string;
  }>;
};

describe("useMutationsAccesses", () => {
  const onSuccessAccessOrInvitation = jest.fn();
  let capturedHooks: CapturedHooks;

  beforeEach(() => {
    mockedUseMutation.mockClear();
    mockedGetDriver.mockReturnValue(driver as never);
    mockedUseOnSuccessAccessOrInvitationMutation.mockReturnValue(
      onSuccessAccessOrInvitation,
    );
    onSuccessAccessOrInvitation.mockReset();
    Object.values(driver).forEach((fn) => fn.mockReset());
    capturedHooks = {
      createAccess: useMutationCreateAccess() as unknown as CapturedHooks["createAccess"],
      createInvitation:
        useMutationCreateInvitation() as unknown as CapturedHooks["createInvitation"],
      updateInvitation:
        useMutationUpdateInvitation() as unknown as CapturedHooks["updateInvitation"],
      updateAccess: useMutationUpdateAccess() as unknown as CapturedHooks["updateAccess"],
      deleteAccess: useMutationDeleteAccess() as unknown as CapturedHooks["deleteAccess"],
      deleteInvitation:
        useMutationDeleteInvitation() as unknown as CapturedHooks["deleteInvitation"],
    };
  });

  it("wires the driver mutation functions and refreshes accesses vs invitations coherently", async () => {
    driver.createAccess.mockResolvedValue(undefined);
    driver.createInvitation.mockResolvedValue(undefined);
    driver.updateInvitation.mockResolvedValue(undefined);
    driver.updateAccess.mockResolvedValue(undefined);
    driver.deleteAccess.mockResolvedValue(undefined);
    driver.deleteInvitation.mockResolvedValue(undefined);

    const createAccessVars = {
      itemId: "item-1",
      userId: "user-1",
      role: Role.EDITOR,
    };
    const createInvitationVars = {
      itemId: "item-1",
      email: "guest@example.test",
      role: Role.READER,
    };
    const updateInvitationVars = {
      itemId: "item-1",
      invitationId: "inv-1",
      role: Role.EDITOR,
    };
    const updateAccessVars = {
      itemId: "item-1",
      accessId: "acc-1",
      user_id: "user-1",
      role: Role.ADMIN,
    };
    const deleteAccessVars = {
      itemId: "item-1",
      accessId: "acc-1",
    };
    const deleteInvitationVars = {
      itemId: "item-1",
      invitationId: "inv-1",
    };

    await capturedHooks.createAccess.mutationFn(createAccessVars);
    capturedHooks.createAccess.onSuccess(undefined, createAccessVars);
    await capturedHooks.createInvitation.mutationFn(createInvitationVars);
    capturedHooks.createInvitation.onSuccess(undefined, createInvitationVars);
    await capturedHooks.updateInvitation.mutationFn(updateInvitationVars);
    capturedHooks.updateInvitation.onSuccess(undefined, updateInvitationVars);
    await capturedHooks.updateAccess.mutationFn(updateAccessVars);
    capturedHooks.updateAccess.onSuccess(undefined, updateAccessVars);
    await capturedHooks.deleteAccess.mutationFn(deleteAccessVars);
    capturedHooks.deleteAccess.onSuccess(undefined, deleteAccessVars);
    await capturedHooks.deleteInvitation.mutationFn(deleteInvitationVars);
    capturedHooks.deleteInvitation.onSuccess(undefined, deleteInvitationVars);

    expect(driver.createAccess).toHaveBeenCalledWith(createAccessVars);
    expect(driver.createInvitation).toHaveBeenCalledWith(createInvitationVars);
    expect(driver.updateInvitation).toHaveBeenCalledWith(updateInvitationVars);
    expect(driver.updateAccess).toHaveBeenCalledWith(updateAccessVars);
    expect(driver.deleteAccess).toHaveBeenCalledWith(deleteAccessVars);
    expect(driver.deleteInvitation).toHaveBeenCalledWith(deleteInvitationVars);

    expect(onSuccessAccessOrInvitation).toHaveBeenNthCalledWith(
      1,
      "item-1",
      false,
    );
    expect(onSuccessAccessOrInvitation).toHaveBeenNthCalledWith(
      2,
      "item-1",
      true,
    );
    expect(onSuccessAccessOrInvitation).toHaveBeenNthCalledWith(
      3,
      "item-1",
      true,
    );
    expect(onSuccessAccessOrInvitation).toHaveBeenNthCalledWith(
      4,
      "item-1",
      false,
    );
    expect(onSuccessAccessOrInvitation).toHaveBeenNthCalledWith(
      5,
      "item-1",
      false,
    );
    expect(onSuccessAccessOrInvitation).toHaveBeenNthCalledWith(
      6,
      "item-1",
      true,
    );
  });
});
