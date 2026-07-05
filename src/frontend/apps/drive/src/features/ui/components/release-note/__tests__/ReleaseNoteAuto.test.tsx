import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { useConfig } from "@/features/config/ConfigProvider";

import { ReleaseNoteAuto } from "../ReleaseNoteAuto";
import { useReleaseNote } from "../useReleaseNote";

const renderedModals: Array<Record<string, unknown>> = [];

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  ReleaseNoteModal: (props: {
    isOpen: boolean;
    appName: string;
    mainTitle: string;
    steps: unknown[];
    footerLink: { label: string; href: string };
    onClose: () => Promise<void>;
    onComplete: () => Promise<void>;
  }) => {
    renderedModals.push(props as Record<string, unknown>);
    return (
      <div>
        release-note-modal:{String(props.isOpen)}:{props.appName}:{props.mainTitle}:
        {props.steps.length}
      </div>
    );
  },
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => `translated:${key}`,
  }),
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: jest.fn(),
}));

jest.mock("../useReleaseNote", () => ({
  useReleaseNote: jest.fn(),
}));

const mockedUseConfig = jest.mocked(useConfig);
const mockedUseReleaseNote = jest.mocked(useReleaseNote);

describe("ReleaseNoteAuto", () => {
  beforeEach(() => {
    renderedModals.length = 0;
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_RELEASE_NOTE_ENABLED: true,
      },
    } as never);
    mockedUseReleaseNote.mockReturnValue({
      currentVersion: "1.0.0",
      mainTitle: "main-title",
      markAsSeen: jest.fn(),
      shouldShow: true,
      steps: [{ title: "step-1" }],
    } as never);
  });

  it("does not render when release notes are disabled in config", () => {
    mockedUseConfig.mockReturnValue({
      config: {
        FRONTEND_RELEASE_NOTE_ENABLED: false,
      },
    } as never);

    const html = renderToStaticMarkup(<ReleaseNoteAuto />);

    expect(html).toBe("");
    expect(renderedModals).toHaveLength(0);
  });

  it("does not render when the hook says there is nothing to show", () => {
    mockedUseReleaseNote.mockReturnValue({
      currentVersion: "1.0.0",
      mainTitle: "main-title",
      markAsSeen: jest.fn(),
      shouldShow: false,
      steps: [],
    } as never);

    const html = renderToStaticMarkup(<ReleaseNoteAuto />);

    expect(html).toBe("");
    expect(renderedModals).toHaveLength(0);
  });

  it("wires the modal props and keeps close callbacks on markAsSeen", async () => {
    const markAsSeen = jest.fn(async () => undefined);
    mockedUseReleaseNote.mockReturnValue({
      currentVersion: "1.0.0",
      mainTitle: "main-title",
      markAsSeen,
      shouldShow: true,
      steps: [{ title: "step-1" }, { title: "step-2" }],
    } as never);

    const html = renderToStaticMarkup(<ReleaseNoteAuto />);
    const modal = renderedModals[0] as {
      appName: string;
      footerLink: { href: string; label: string };
      mainTitle: string;
      onClose: () => Promise<void>;
      onComplete: () => Promise<void>;
      steps: unknown[];
    };

    expect(html).toContain("release-note-modal:false:translated:release_notes.labels.app_name:main-title:2");
    expect(modal.appName).toBe("translated:release_notes.labels.app_name");
    expect(modal.mainTitle).toBe("main-title");
    expect(modal.steps).toHaveLength(2);
    expect(modal.footerLink).toEqual({
      href: "https://docs.numerique.gouv.fr/docs/46085eec-8fd9-4466-98db-b8a40fb545fd/",
      label: "translated:release_notes.labels.see_whats_new",
    });

    await modal.onClose();
    await modal.onComplete();

    expect(markAsSeen).toHaveBeenCalledTimes(2);
  });
});
