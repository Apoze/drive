import { useRouter } from "next/router";
import { ResourcePublicLinksModal } from "@/features/storage/ResourcePublicLinks";
import { useTranslation } from "react-i18next";
import { useState } from "react";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { ItemsBrowseExplorer } from "@/features/explorer/components/items-browse/ItemsBrowseExplorer";
import { MountBrowseExplorer } from "@/features/mounts/components/MountBrowseExplorer";
import { MountFilesPreview } from "@/features/mounts/components/MountFilesPreview";
import { entryToMountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { getParentMountPath } from "@/features/mounts/utils/mountBulkActions";
import { resolveExplorerFileOpenAction } from "@/features/explorer/utils/fileOpenAction";
import {
  CustomFilesPreview,
  CustomFilesPreviewMode,
} from "@/features/ui/preview/custom-files-preview/CustomFilesPreview";
import {
  resourceItem,
  resolveLegacyMount,
  useStorageResource,
} from "@/features/storage/api";

export default function ResourcePage() {
  const router = useRouter();
  const { t } = useTranslation();
  const id = typeof router.query.id === "string" ? router.query.id : undefined;
  const space =
    typeof router.query.space === "string" ? router.query.space : undefined;
  const query = useStorageResource(id, space);
  const [navigationError, setNavigationError] = useState(false);
  if (query.isError)
    return (
      <p role="alert">
        {t("storage.load_error")}{" "}
        <Button
          variant="tertiary"
          onClick={() => {
            void query.refetch();
          }}
        >
          {t("common.retry")}
        </Button>
      </p>
    );
  if (!query.data) return <p role="status">{t("storage.loading")}</p>;
  const resource = query.data;
  if (resource.kind === "docs" && resource.adapter.kind === "item") {
    const action = resolveExplorerFileOpenAction({
      item: resourceItem(resource),
    });
    return (
      <>
        <h1>{resource.title}</h1>
        {action.type === "docs-new-tab" ? (
          <a href={action.url} target="_blank" rel="noopener noreferrer">
            {t("storage.open")} Docs
          </a>
        ) : (
          <p role="status">{t("storage.load_error")}</p>
        )}
        <ItemsBrowseExplorer
          kind="children"
          itemId={resource.id}
          navigationId={resource.id}
        />
      </>
    );
  }
  const sharing =
    router.query.share === "true" ? (
      <ResourcePublicLinksModal
        resourceId={resource.id}
        space={resource.space}
        title={resource.title}
        canCreate={
          resource.adapter.kind === "mount" &&
          resource.adapter.entry.abilities?.share_link_create === true
        }
        onClose={() => {
          const query = { ...router.query };
          delete query.share;
          void router.replace({ pathname: router.pathname, query }, undefined, {
            shallow: true,
          });
        }}
      />
    ) : null;
  if (sharing) return sharing;
  if (resource.adapter.kind === "item")
    return (
      <>
        {resource.kind === "folder" ? (
          <ItemsBrowseExplorer
            kind="children"
            itemId={resource.id}
            navigationId={resource.id}
          />
        ) : (
          <CustomFilesPreview
            currentItem={resourceItem(resource)}
            items={[resourceItem(resource)]}
            mode={CustomFilesPreviewMode.CONTEXTUAL}
          />
        )}
      </>
    );
  const adapter = resource.adapter;
  const navigate = (path: string) => {
    setNavigationError(false);
    void resolveLegacyMount(adapter.mount_id, path)
      .then((target) => router.push(target.href))
      .catch(() => setNavigationError(true));
  };
  const file =
    resource.kind === "file"
      ? entryToMountExplorerItem(
          adapter.mount_id,
          adapter.entry,
          resource.title,
        )
      : undefined;
  const parentPath = getParentMountPath(adapter.path) ?? "/";
  return (
    <>
      {navigationError && <p role="alert">{t("storage.load_error")}</p>}
      <MountBrowseExplorer
        unified
        resource={file ? undefined : resource}
        mountId={adapter.mount_id}
        path={file ? parentPath : adapter.path}
        onNavigateToPath={navigate}
      />
      {file && (
        <MountFilesPreview
          currentItem={file}
          items={[file]}
          setPreviewCurrentItem={(next) => {
            if (!next) navigate(parentPath);
          }}
        />
      )}
    </>
  );
}
ResourcePage.getLayout = getGlobalExplorerLayout;
