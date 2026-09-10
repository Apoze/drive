import React from "react";
import { fetchAPI } from "@/features/api/fetchApi";
import { useRouter } from "next/router";
import { useEffect, useMemo, useState } from "react";
import { getPublicMountShareError } from "@/features/routing/shareRouteRuntime";
import { baseApiUrl } from "@/features/api/utils";
import { useTranslation } from "react-i18next";
import Head from "next/head";

type PublicMountShareEntry = {
  normalized_path: string;
  entry_type: "file" | "folder" | "docs";
  name: string;
  size?: number | null;
  modified_at?: string | null;
  download_available?: boolean;
  url_docs?: string | null;
};

type BrowseResponse = {
  normalized_path: string;
  entry: PublicMountShareEntry;
  children: null | {
    count: number;
    next: string | null;
    previous: string | null;
    results: PublicMountShareEntry[];
  };
};

const SHARE_OPEN_TIMEOUT_MS = 15000;

export default function MountShareLinkPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const rawOffset = Number(router.query.offset || 0);
  const offset =
    Number.isSafeInteger(rawOffset) && rawOffset >= 0 ? rawOffset : 0;

  const token = useMemo(() => {
    const raw = router.query.token;
    return typeof raw === "string" ? raw : null;
  }, [router.query.token]);

  const path = useMemo(() => {
    const raw = router.query.path;
    return typeof raw === "string" ? raw : null;
  }, [router.query.path]);

  const [data, setData] = useState<BrowseResponse | null>(null);
  const [error, setError] = useState<
    "not_found" | "gone" | "timeout" | "unknown" | null
  >(null);
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!token) {
      return;
    }

    setLoading(true);
    setError(null);
    setData(null);
    let active = true;

    fetchAPI(
      `mount-share-links/${token}/browse/`,
      { params: { path: path || "/", offset, limit: 50 } },
      { redirectOn40x: false, timeoutMs: SHARE_OPEN_TIMEOUT_MS },
    )
      .then((r) => r.json())
      .then((payload) => {
        if (active) setData(payload);
      })
      .catch((e) => {
        if (active) setError(getPublicMountShareError(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, token, offset, retry]);

  if (!token) {
    return null;
  }

  if (loading) {
    return (
      <main style={{ padding: 24 }}>
        <h1>{t("storage.loading")}</h1>
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ padding: 24 }}>
        <h1>{t("storage.public_share.unavailable")}</h1>
        {error === "gone" ? (
          <p>{t("storage.public_share.gone")}</p>
        ) : error === "timeout" ? (
          <p>{t("storage.public_share.timeout")}</p>
        ) : (
          <p>{t("storage.public_share.invalid")}</p>
        )}
        <button type="button" onClick={() => setRetry((value) => value + 1)}>
          {t("common.retry")}
        </button>
      </main>
    );
  }

  if (!data) {
    return null;
  }

  const current = data.entry;
  const children = data.children?.results ?? [];
  const navigate = (nextPath: string, nextOffset = 0) =>
    router.push(
      {
        pathname: router.pathname,
        query: {
          token,
          path: nextPath,
          ...(nextOffset ? { offset: nextOffset } : {}),
        },
      },
      undefined,
      { shallow: true },
    );
  const download = `${baseApiUrl()}mount-share-links/${encodeURIComponent(token)}/download/?${new URLSearchParams({ path: current.normalized_path })}`;

  return (
    <main style={{ padding: 24, maxWidth: 900, margin: "0 auto" }}>
      <Head>
        <meta name="referrer" content="no-referrer" />
      </Head>
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ marginBottom: 8 }}>{current.name}</h1>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {data.normalized_path !== "/" && (
            <button type="button" onClick={() => navigate("/")}>
              {t("storage.public_share.root")}
            </button>
          )}
        </div>
      </header>

      {current.entry_type === "folder" && (
        <section>
          <h2 style={{ marginBottom: 8 }}>
            {t("storage.public_share.contents")}
          </h2>
          {children.length === 0 ? (
            <p>{t("storage.public_share.empty")}</p>
          ) : (
            <ul style={{ paddingLeft: 18 }}>
              {children.map((child) => (
                <li
                  key={`${child.entry_type}:${child.normalized_path}`}
                  style={{ marginBottom: 6 }}
                >
                  {child.url_docs ? (
                    <a href={child.url_docs} target="_blank" rel="noreferrer">
                      {child.name}
                    </a>
                  ) : (
                    <button
                      type="button"
                      onClick={() => navigate(child.normalized_path)}
                    >
                      {child.name}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {data.children && data.children.count > 50 && (
            <nav aria-label={t("storage.public_share.contents")}>
              <button
                type="button"
                disabled={!offset}
                onClick={() =>
                  navigate(data.normalized_path, Math.max(0, offset - 50))
                }
              >
                {t("storage.transfers.previous")}
              </button>
              <button
                type="button"
                disabled={!data.children.next}
                onClick={() => navigate(data.normalized_path, offset + 50)}
              >
                {t("storage.transfers.next")}
              </button>
            </nav>
          )}
        </section>
      )}

      {(current.entry_type === "file" || current.download_available) && (
        <section>
          {current.download_available ? (
            <a href={download} rel="noreferrer">
              {t("storage.public_share.download")}
            </a>
          ) : (
            <p>{t("storage.public_share.download_unavailable")}</p>
          )}
        </section>
      )}
    </main>
  );
}
