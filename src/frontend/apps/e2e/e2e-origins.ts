type Env = Record<string, string | undefined>;

export type E2EOrigins = {
  baseURL: string;
  apiOrigin: string;
  edgeOrigin: string;
  s3Origin: string;
};

const LOOPBACK_HOST = "127.0.0.1";
const DEFAULT_LAN_HOST = "192.168.10.123";

const trimTrailingSlash = (origin: string) => origin.replace(/\/$/, "");

const isExplicitLanMode = (env: Env) => {
  const networkMode = env.E2E_NETWORK_MODE?.toLowerCase();
  return env.ENV_OVERRIDE === "local" || networkMode === "lan";
};

const getHost = (env: Env) => {
  if (isExplicitLanMode(env)) {
    return env.E2E_LAN_HOST || DEFAULT_LAN_HOST;
  }
  return env.E2E_LOOPBACK_HOST || LOOPBACK_HOST;
};

const buildDefaultOrigins = (env: Env): E2EOrigins => {
  const host = getHost(env);
  const frontendPort = env.PORT || "3000";
  return {
    baseURL: `http://${host}:${frontendPort}`,
    apiOrigin: `http://${host}:8071`,
    edgeOrigin: `http://${host}:8083`,
    s3Origin: `http://${host}:9000`,
  };
};

export const getE2EOrigins = (env: Env = process.env): E2EOrigins => {
  const defaults = buildDefaultOrigins(env);
  return {
    baseURL: trimTrailingSlash(env.E2E_BASE_URL || defaults.baseURL),
    apiOrigin: trimTrailingSlash(env.E2E_API_ORIGIN || defaults.apiOrigin),
    edgeOrigin: trimTrailingSlash(env.E2E_EDGE_ORIGIN || defaults.edgeOrigin),
    s3Origin: trimTrailingSlash(env.E2E_S3_ORIGIN || defaults.s3Origin),
  };
};

export const getE2EBaseURL = (env: Env = process.env) =>
  getE2EOrigins(env).baseURL;

export const getE2EApiOrigin = (env: Env = process.env) =>
  getE2EOrigins(env).apiOrigin;
