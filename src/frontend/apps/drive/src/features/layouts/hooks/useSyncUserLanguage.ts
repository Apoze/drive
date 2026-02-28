import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/features/auth/Auth";
import { getDriver } from "@/features/config/Config";
import { LANGUAGES } from "../components/header/Header";

/**
 * Auto-sync browser language to backend for new users whose
 * language field is null (e.g. just created via OIDC).
 */
export const useSyncUserLanguage = () => {
  const { user, refreshUser } = useAuth();
  const { i18n } = useTranslation();
  const driver = getDriver();

  useEffect(() => {
    if (!user) return;

    // If the backend already knows the user's preferred language, keep the UI aligned.
    // Note: backend stores language codes in lowercase (e.g. "fr-fr"), while i18next may
    // use a normalized/uppercased region code (e.g. "fr-FR").
    if (user.language) {
      const userLang = user.language.toLowerCase();
      const currentLang = i18n.language?.toLowerCase();

      if (currentLang !== userLang) {
        void i18n.changeLanguage(userLang).catch(() => undefined);
      }
      return;
    }

    const detectedLang = i18n.language?.toLowerCase();
    if (!detectedLang) {
      return;
    }

    const language = LANGUAGES.find((lang) => lang.value === detectedLang);
    if (!language) {
      return;
    }

    driver.updateUser({ language: language.value, id: user.id }).then(() => {
      void refreshUser?.();
    });
  }, [user, i18n.language, driver, refreshUser]);
};
