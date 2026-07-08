import { login } from "@/features/auth/Auth";
import { SESSION_STORAGE_REDIRECT_AFTER_LOGIN_URL } from "@/features/api/fetchApi";
import { useConfig } from "@/features/config/ConfigProvider";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";

export const AnonymousCTA = () => {
  const { t } = useTranslation();
  const { config } = useConfig();
  const tryOutUrl = config.FRONTEND_EXTERNAL_HOME_URL ?? "/";

  const handleLogin = () => {
    sessionStorage.setItem(
      SESSION_STORAGE_REDIRECT_AFTER_LOGIN_URL,
      window.location.href,
    );
    login();
  };

  return (
    <div className="anonymous-cta">
      <div className="anonymous-cta__separator" />
      <Button
        variant="tertiary"
        size="small"
        href={tryOutUrl}
        id="anonymous-cta-try-out"
        data-testid="anonymous-cta-try-out"
      >
        {t("anonymous_cta.try_out")}
      </Button>
      <Button
        variant="primary"
        size="small"
        onClick={handleLogin}
        data-testid="anonymous-cta-login"
      >
        {t("anonymous_cta.login")}
      </Button>
    </div>
  );
};
