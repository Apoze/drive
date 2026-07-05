import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { fetchAPI } from "@/features/api/fetchApi";
import { useAuth } from "@/features/auth/Auth";

import { CURRENT_RELEASE_NOTE, CURRENT_VERSION } from "../releaseNotes.config";
import { buildStepsFromConfig, useReleaseNote } from "../useReleaseNote";

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/features/api/fetchApi", () => ({
  fetchAPI: jest.fn(),
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedUseAuth = jest.mocked(useAuth);
const mockedFetchAPI = jest.mocked(fetchAPI);

let capturedHook: ReturnType<typeof useReleaseNote> | null = null;

const ReleaseNoteProbe = () => {
  capturedHook = useReleaseNote();
  return <div>release-note-probe</div>;
};

describe("useReleaseNote", () => {
  beforeEach(() => {
    capturedHook = null;
    mockedFetchAPI.mockReset();
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
    mockedUseAuth.mockReturnValue({
      user: null,
      refreshUser: jest.fn(),
    } as never);
  });

  it("builds translated steps from the release-note config", () => {
    expect(CURRENT_RELEASE_NOTE).toBeDefined();

    const steps = buildStepsFromConfig(CURRENT_RELEASE_NOTE!, (key) => `t:${key}`);

    expect(steps).toHaveLength(CURRENT_RELEASE_NOTE!.steps.length);
    expect(steps[0]).toEqual(
      expect.objectContaining({
        description: `t:${CURRENT_RELEASE_NOTE!.steps[0].descriptionKey}`,
        title: `t:${CURRENT_RELEASE_NOTE!.steps[0].titleKey}`,
      }),
    );
  });

  it("stays hidden when there is no authenticated user", () => {
    renderToStaticMarkup(<ReleaseNoteProbe />);

    expect(capturedHook?.shouldShow).toBe(false);
    expect(capturedHook?.mainTitle).toBe(
      `translated:${CURRENT_RELEASE_NOTE?.mainTitleKey}`,
    );
    expect(capturedHook?.steps).toHaveLength(CURRENT_RELEASE_NOTE?.steps.length ?? 0);
  });

  it("stays hidden when the current release was already seen", () => {
    mockedUseAuth.mockReturnValue({
      refreshUser: jest.fn(),
      user: {
        id: "user-1",
        last_release_note_seen: CURRENT_VERSION,
      },
    } as never);

    renderToStaticMarkup(<ReleaseNoteProbe />);

    expect(capturedHook?.shouldShow).toBe(false);
  });

  it("shows the note when the current version was not seen yet", () => {
    mockedUseAuth.mockReturnValue({
      refreshUser: jest.fn(),
      user: {
        id: "user-1",
        last_release_note_seen: "0.0.0",
      },
    } as never);

    renderToStaticMarkup(<ReleaseNoteProbe />);

    expect(capturedHook?.shouldShow).toBe(true);
    expect(capturedHook?.currentVersion).toBe(CURRENT_VERSION);
  });

  it("marks the current version as seen and refreshes the user", async () => {
    const refreshUser = jest.fn();
    mockedUseAuth.mockReturnValue({
      refreshUser,
      user: {
        id: "user-42",
        last_release_note_seen: "0.0.0",
      },
    } as never);

    renderToStaticMarkup(<ReleaseNoteProbe />);

    await capturedHook?.markAsSeen();

    expect(mockedFetchAPI).toHaveBeenCalledWith("users/user-42/", {
      body: JSON.stringify({
        last_release_note_seen: CURRENT_VERSION,
      }),
      method: "PATCH",
    });
    expect(refreshUser).toHaveBeenCalledTimes(1);
  });
});
