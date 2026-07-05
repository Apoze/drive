import { useConfig } from "@/features/config/ConfigProvider";
import { ThemeCustomization } from "@/features/drivers/types";
import { useTranslation } from "react-i18next";
import { resolveLocalizedThemeCustomization } from "./themeCustomizationRuntime";

export const useThemeCustomization = (key: keyof ThemeCustomization) => {
  const { config } = useConfig();
  const { i18n } = useTranslation();

  return resolveLocalizedThemeCustomization(
    config?.theme_customization?.[key],
    i18n.language,
  );
};
