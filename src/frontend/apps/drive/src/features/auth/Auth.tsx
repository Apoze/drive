import React, { PropsWithChildren, useEffect, useState } from "react";

import { fetchAPI } from "@/features/api/fetchApi";
import { User } from "@/features/auth/types";
import { baseApiUrl } from "../api/utils";
import { posthog } from "posthog-js";
import { SpinnerPage } from "@/features/ui/components/spinner/SpinnerPage";
import { attemptSilentLogin, canAttemptSilentLogin } from "./silentLogin";
import { authUrl } from "./authUrl";
import { useConfig } from "../config/ConfigProvider";
import {
  resolveAuthInitOutcome,
  syncPosthogIdentity,
} from "./authRuntime";

export const logout = () => {
  window.location.replace(new URL("logout/", baseApiUrl()).href);
  posthog.reset();
};

export const login = (returnTo?: string) => {
  const url = authUrl({ returnTo });
  window.location.replace(url.href);
};

interface AuthContextInterface {
  user?: User | null;
  init?: () => Promise<User | null>;
  refreshUser?: () => Promise<void>;
}

export const AuthContext = React.createContext<AuthContextInterface>({});

export const useAuth = () => React.useContext(AuthContext);

export const Auth = ({
  children,
}: PropsWithChildren & { redirect?: boolean }) => {
  const [user, setUser] = useState<User | null>();
  const { config } = useConfig();

  const init = async () => {
    const outcome = await resolveAuthInitOutcome({
      attemptSilentLogin,
      canAttemptSilentLogin,
      fetchMe: async () => {
        const response = await fetchAPI(`users/me/`, undefined, {
          redirectOn40x: false,
        });
        return (await response.json()) as User;
      },
      silentLoginEnabled: config.FRONTEND_SILENT_LOGIN_ENABLED,
    });

    if (outcome.kind === "user") {
      setUser(outcome.user);
      return outcome.user;
    }

    if (outcome.kind === "anonymous") {
      setUser(null);
      return null;
    }

    return null;
  };

  const refreshUser = async () => {
    void init();
  };

  useEffect(() => {
    void init();
  }, []);

  useEffect(() => {
    syncPosthogIdentity(posthog, user);
  }, [user]);

  if (user === undefined) {
    return <SpinnerPage />;
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        init,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
