import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/features/auth/Auth";
import { getDriver } from "@/features/config/Config";

import { useSyncUserLanguage } from "../useSyncUserLanguage";

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@/features/layouts/components/header/Header", () => ({
  LANGUAGES: [
    { label: "Français", value: "fr-fr" },
    { label: "English", value: "en-us" },
  ],
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedUseAuth = jest.mocked(useAuth);
const mockedGetDriver = jest.mocked(getDriver);

const Probe = () => {
  useSyncUserLanguage();
  return <div>probe</div>;
};

describe("useSyncUserLanguage", () => {
  const updateUser = jest.fn();
  const changeLanguage = jest.fn();
  const refreshUser = jest.fn();

  beforeEach(() => {
    updateUser.mockReset();
    changeLanguage.mockReset();
    refreshUser.mockReset();
    changeLanguage.mockResolvedValue(undefined);
    mockedGetDriver.mockReturnValue({
      updateUser,
    } as never);
  });

  it("syncs frontend language to the backend for users without a language", async () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    updateUser.mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      refreshUser,
      user: {
        id: "user-1",
        language: null,
      },
    } as never);
    mockedUseTranslation.mockReturnValue({
      i18n: {
        changeLanguage,
        language: "fr-fr",
      },
    } as never);

    renderToStaticMarkup(<Probe />);
    await Promise.resolve();

    expect(updateUser).toHaveBeenCalledWith({
      id: "user-1",
      language: "fr-fr",
    });
    expect(refreshUser).toHaveBeenCalledTimes(1);

    useEffectSpy.mockRestore();
  });

  it("syncs backend language to the frontend when the user already has one", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    mockedUseAuth.mockReturnValue({
      refreshUser,
      user: {
        id: "user-1",
        language: "en-us",
      },
    } as never);
    mockedUseTranslation.mockReturnValue({
      i18n: {
        changeLanguage,
        language: "fr-fr",
      },
    } as never);

    renderToStaticMarkup(<Probe />);

    expect(changeLanguage).toHaveBeenCalledWith("en-us");
    expect(updateUser).not.toHaveBeenCalled();

    useEffectSpy.mockRestore();
  });

  it("does nothing when there is no user", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    mockedUseAuth.mockReturnValue({
      refreshUser,
      user: null,
    } as never);
    mockedUseTranslation.mockReturnValue({
      i18n: {
        changeLanguage,
        language: "fr-fr",
      },
    } as never);

    renderToStaticMarkup(<Probe />);

    expect(changeLanguage).not.toHaveBeenCalled();
    expect(updateUser).not.toHaveBeenCalled();

    useEffectSpy.mockRestore();
  });

  it("does nothing when the detected frontend language is unsupported", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    mockedUseAuth.mockReturnValue({
      refreshUser,
      user: {
        id: "user-1",
        language: null,
      },
    } as never);
    mockedUseTranslation.mockReturnValue({
      i18n: {
        changeLanguage,
        language: "es-es",
      },
    } as never);

    renderToStaticMarkup(<Probe />);

    expect(updateUser).not.toHaveBeenCalled();

    useEffectSpy.mockRestore();
  });
});
