import { LocalizedThemeCustomization } from "@/features/drivers/types";
import { splitLocaleCode } from "@/features/i18n/utils";

export const resolveLocalizedThemeCustomization = <T extends object>(
  themeCustomization: LocalizedThemeCustomization<T> | undefined,
  language: string,
): Partial<T> => {
  const localeLanguage = splitLocaleCode(language).language;

  return {
    ...(themeCustomization?.default ?? {}),
    ...(themeCustomization?.[localeLanguage] ?? {}),
  };
};
