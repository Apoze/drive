import React from "react";
import { Auth, login, useAuth } from "@/features/auth/Auth";
import { GlobalExplorerProvider } from "@/features/explorer/components/GlobalExplorerContext";
import { HorizontalSeparator, Spinner } from "@gouvfr-lasuite/ui-kit";
import { createContext, useContext, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useRouter } from "next/router";

export const getSdkLayout = (page: React.ReactElement, requireLogin = false) => {
  return <SdkLayout requireLogin={requireLogin}>{page}</SdkLayout>;
};

export const SdkContext = createContext<{
  token: string;
}>({
  token: "",
});

export const useSdkContext = () => {
  const context = useContext(SdkContext);
  if (!context) {
    throw new Error("useSdkContext must be used within a SdkContext");
  }
  return context;
};

/**
 * SDK.
 */

const SdkLoginGate = ({ children }: { children: React.ReactNode }) => {
  const { user } = useAuth();
  useEffect(() => { if (user === null) login(window.location.href); }, [user]);
  return user ? <>{children}</> : <Spinner size="xl" />;
};

export const SdkLayout = ({ children, requireLogin = false }: { children: React.ReactNode; requireLogin?: boolean }) => {
  const { t } = useTranslation();
  const router = useRouter();

  const content = <>
        <div className="sdk__explorer__header">
          {t(requireLogin && router.query.mode === "folder" ? "transfer_intake.destination" : "sdk.explorer.picker_caption")}
        </div>
        <HorizontalSeparator />
        {children}
      </>;
  const explorer = (
      <GlobalExplorerProvider displayMode="sdk" itemId="" onNavigate={() => {}}>
        {requireLogin ? <div className="suite-picker-layout" style={{ height: "100dvh", display: "flex", flexDirection: "column", overflow: "hidden" }}>{content}</div> : content}
      </GlobalExplorerProvider>
  );
  return <Auth>{requireLogin ? <SdkLoginGate>{explorer}</SdkLoginGate> : explorer}</Auth>;
};

/**
 * Picker.
 */

export const getSdkPickerLayout = (page: React.ReactElement) => {
  return <SdkPickerLayout>{page}</SdkPickerLayout>;
};

export const SdkPickerLayout = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    setToken(sessionStorage.getItem("sdk_token"));
  }, []);

  if (!token) {
    return <Spinner size="xl" />;
  }

  return (
    <SdkContext.Provider value={{ token }}>
      <SdkLayout>{children}</SdkLayout>
    </SdkContext.Provider>
  );
};
