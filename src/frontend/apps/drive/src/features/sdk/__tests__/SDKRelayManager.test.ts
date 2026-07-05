import { fetchAPI } from "@/features/api/fetchApi";

import { ClientMessageType, SDKRelayManager } from "../SdkRelayManager";

jest.mock("@/features/api/fetchApi", () => ({
  fetchAPI: jest.fn(),
}));

const mockedFetchAPI = jest.mocked(fetchAPI);

describe("SDKRelayManager", () => {
  it("forwards SDK relay events through fetchAPI", async () => {
    mockedFetchAPI.mockResolvedValue({ ok: true } as never);

    await SDKRelayManager.registerEvent("sdk-token", {
      data: {
        items: [{ id: "item-1" }],
      },
      type: ClientMessageType.ITEMS_SELECTED,
    });

    expect(mockedFetchAPI).toHaveBeenCalledWith(
      "sdk-relay/events/",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(
      JSON.parse((mockedFetchAPI.mock.calls[0]?.[1] as { body: string }).body),
    ).toEqual({
      event: {
        data: {
          items: [{ id: "item-1" }],
        },
        type: ClientMessageType.ITEMS_SELECTED,
      },
      token: "sdk-token",
    });
  });
});
