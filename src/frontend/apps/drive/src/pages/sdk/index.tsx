import React from "react";
import { Spinner } from "@gouvfr-lasuite/ui-kit";
import { useEffect } from "react";
import { login, useAuth } from "@/features/auth/Auth";
import { GlobalLayout } from "@/features/layouts/components/global/GlobalLayout";
import { useSearchParams } from "next/navigation";
import {
  buildSdkExplorerRedirectUrl,
  resolveSdkLandingAction,
} from "@/features/sdk/sdkRuntime";

export default function SDKPage() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const mode = searchParams.get("mode");
  const token = searchParams.get("token");

  useEffect(() => {
    const action = resolveSdkLandingAction({
      currentHref: window.location.href,
      mode,
      token,
      user,
    });

    if (action.kind === "missing_token") {
      throw new Error("Token is required");
    }

    sessionStorage.setItem("sdk_token", action.token);

    if (action.kind === "redirect") {
      window.location.href = buildSdkExplorerRedirectUrl(action.mode);
      return;
    }

    login(action.returnTo);
  }, [user]);

  return (
    <div className="sdk__page">
      <Spinner size="xl" />
    </div>
  );
}

SDKPage.getLayout = function getLayout(page: React.ReactElement) {
  return <GlobalLayout>{page}</GlobalLayout>;
};
