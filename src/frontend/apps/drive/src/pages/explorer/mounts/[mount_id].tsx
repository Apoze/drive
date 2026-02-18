import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { getDriver } from "@/features/config/Config";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import type { MountVirtualEntry } from "@/features/drivers/types";
import { errorToString } from "@/features/api/APIError";
import { getOrigin } from "@/features/api/utils";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";

const DEFAULT_LIMIT = 20;

function getParentPath(path: string) {
  if (path === "/") {
    return "/";
  }
  const parts = path.split("/").filter(Boolean);
  parts.pop();
  return `/${parts.join("/")}` || "/";
}

function MountAction(props: {
  label: string;
  capabilityEnabled: boolean;
  abilityEnabled: boolean;
  onClick?: () => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();

  if (!props.capabilityEnabled) {
    return null;
  }

  const isDisabled = Boolean(props.disabled) || !props.abilityEnabled;

  if (!props.abilityEnabled) {
    return (
      <div>
        <Button variant="tertiary" disabled>
          {props.label}
        </Button>
        <div>{t("explorer.mounts.actions.unavailable")}</div>
      </div>
    );
  }

  return (
    <div>
      <Button variant="tertiary" disabled={isDisabled} onClick={props.onClick}>
        {props.label}
      </Button>
    </div>
  );
}

export default function MountBrowsePage() {
  const { t } = useTranslation();
  const router = useRouter();
  const mountId = String(router.query.mount_id ?? "");

  const [path, setPath] = useState("/");
  const [offset, setOffset] = useState(0);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [shareLoading, setShareLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const {
    data: browse,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["mounts", "browse", mountId, path, DEFAULT_LIMIT, offset],
    enabled: Boolean(mountId),
    refetchOnWindowFocus: false,
    queryFn: () =>
      getDriver().browseMount({
        mountId,
        path,
        limit: DEFAULT_LIMIT,
        offset,
      }),
  });

  const children = browse?.children?.results ?? null;
  const count = browse?.children?.count ?? null;

  const canPrev = useMemo(() => offset > 0, [offset]);
  const canNext = useMemo(() => {
    if (count === null) {
      return false;
    }
    return offset + DEFAULT_LIMIT < count;
  }, [count, offset]);

  useEffect(() => {
    if (!router.isReady) {
      return;
    }
    const q = router.query.path;
    const nextPath = typeof q === "string" && q ? q : "/";
    setPath(nextPath);
    setOffset(0);
  }, [router.isReady, router.query.path]);

  const onNavigateToEntry = (entry: MountVirtualEntry) => {
    void router.replace(
      {
        pathname: "/explorer/mounts/[mount_id]",
        query: { mount_id: mountId, path: entry.normalized_path },
      },
      undefined,
      { shallow: true },
    );
  };

  const onPreviewEntry = (entry: MountVirtualEntry) => {
    router.push({
      pathname: "/explorer/mounts/[mount_id]/preview",
      query: { mount_id: mountId, path: entry.normalized_path },
    });
  };

  if (isLoading) {
    return <div>{t("explorer.mounts.browse_loading")}</div>;
  }

  if (isError || !browse) {
    return (
      <div>
        <div>{t("explorer.mounts.browse_error")}</div>
        <Button variant="tertiary" onClick={() => refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    );
  }

  const capabilityUpload = Boolean(browse.capabilities?.["mount.upload"]);
  const capabilityPreview = Boolean(browse.capabilities?.["mount.preview"]);
  const capabilityWopi = Boolean(browse.capabilities?.["mount.wopi"]);
  const capabilityShareLink = Boolean(browse.capabilities?.["mount.share_link"]);

  const doUpload = async (file: File) => {
    setUploadLoading(true);
    try {
      await getDriver().uploadMountFile({
        mountId,
        path: browse.normalized_path,
        file,
      });
      addToast(<ToasterItem>{t("explorer.mounts.upload.success")}</ToasterItem>);
      await refetch();
    } catch (e) {
      addToast(<ToasterItem type="error">{errorToString(e)}</ToasterItem>);
    } finally {
      setUploadLoading(false);
      if (uploadInputRef.current) {
        uploadInputRef.current.value = "";
      }
    }
  };

  const createShareLink = async () => {
    setShareLoading(true);
    try {
      const res = await getDriver().createMountShareLink({
        mountId,
        path: browse.normalized_path,
      });
      setShareUrl(res.share_url);
      try {
        await navigator.clipboard.writeText(res.share_url);
      } catch {
        // Ignore clipboard errors; the URL is still rendered for manual copy.
      }
    } finally {
      setShareLoading(false);
    }
  };

  return (
    <div>
      <h1>
        {t("explorer.mounts.title")} — {mountId}
      </h1>

      <div>
        <Link href="/explorer/mounts">{t("explorer.mounts.title")}</Link>
      </div>

      <div>
        {t("explorer.mounts.path")}: <code>{browse.normalized_path}</code>
      </div>

      <div>
        <Button
          variant="tertiary"
          disabled={browse.normalized_path === "/"}
          onClick={() => {
            void router.replace(
              {
                pathname: "/explorer/mounts/[mount_id]",
                query: {
                  mount_id: mountId,
                  path: getParentPath(browse.normalized_path),
                },
              },
              undefined,
              { shallow: true },
            );
          }}
        >
          {t("common.back")}
        </Button>
      </div>

      <h2>{t("explorer.mounts.actions.title")}</h2>
      <input
        ref={uploadInputRef}
        type="file"
        style={{ display: "none" }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            void doUpload(file);
          }
        }}
      />
      {browse.entry.entry_type === "folder" ? (
        <>
          <MountAction
            label={t("explorer.mounts.actions.upload")}
            capabilityEnabled={capabilityUpload}
            abilityEnabled={browse.entry.abilities.upload}
            disabled={uploadLoading}
            onClick={() => uploadInputRef.current?.click()}
          />
          <MountAction
            label={t("explorer.mounts.actions.share")}
            capabilityEnabled={capabilityShareLink}
            abilityEnabled={browse.entry.abilities.share_link_create}
            disabled={shareLoading}
            onClick={createShareLink}
          />
        </>
      ) : (
        <>
          <MountAction
            label={t("explorer.mounts.actions.preview")}
            capabilityEnabled={capabilityPreview}
            abilityEnabled={browse.entry.abilities.preview}
            onClick={() => onPreviewEntry(browse.entry)}
          />
          <MountAction
            label={t("explorer.mounts.actions.download")}
            capabilityEnabled={true}
            abilityEnabled={browse.entry.abilities.download}
            onClick={() => {
              const origin = getOrigin();
              const query = new URLSearchParams({
                path: browse.entry.normalized_path,
              });
              window.open(
                `${origin}/api/v1.0/mounts/${mountId}/download/?${query.toString()}`,
                "_blank",
                "noreferrer",
              );
            }}
          />
          <MountAction
            label={t("explorer.mounts.actions.wopi")}
            capabilityEnabled={capabilityWopi}
            abilityEnabled={browse.entry.abilities.wopi}
            onClick={() =>
              router.push({
                pathname: "/explorer/mounts/[mount_id]/wopi",
                query: { mount_id: mountId, path: browse.entry.normalized_path },
              })
            }
          />
          <MountAction
            label={t("explorer.mounts.actions.share")}
            capabilityEnabled={capabilityShareLink}
            abilityEnabled={browse.entry.abilities.share_link_create}
            disabled={shareLoading}
            onClick={createShareLink}
          />
        </>
      )}

      {shareUrl && (
        <div>
          <div>{t("explorer.mounts.actions.share_url")}:</div>
          <code>{shareUrl}</code>
        </div>
      )}

      <h2>{t("explorer.mounts.children.title")}</h2>
      {children === null ? (
        <div>{t("explorer.mounts.children.none")}</div>
      ) : children.length === 0 ? (
        <div>{t("explorer.mounts.children.empty")}</div>
      ) : (
        <ul>
          {children.map((entry) => (
            <li key={entry.normalized_path}>
              <button type="button" onClick={() => onNavigateToEntry(entry)}>
                {entry.name}
              </button>{" "}
              <code>{entry.normalized_path}</code>
              {entry.entry_type === "file" && (
                <>
                  {" "}
                  <Button
                    variant="tertiary"
                    onClick={() => onPreviewEntry(entry)}
                  >
                    {t("explorer.mounts.actions.preview")}
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {children !== null && (
        <div>
          <Button
            variant="tertiary"
            disabled={!canPrev}
            onClick={() => setOffset(Math.max(0, offset - DEFAULT_LIMIT))}
          >
            {t("common.previous")}
          </Button>
          <Button
            variant="tertiary"
            disabled={!canNext}
            onClick={() => setOffset(offset + DEFAULT_LIMIT)}
          >
            {t("common.next")}
          </Button>
          {count !== null && (
            <span>
              {offset + 1}–{Math.min(offset + DEFAULT_LIMIT, count)} / {count}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

MountBrowsePage.getLayout = getGlobalExplorerLayout;
