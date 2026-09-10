import { defaultArchiveNameForItems } from "@/features/explorer/components/modals/archiveActionSubmitControllers";
import { useRef, useState } from "react";
import { operationId as uuid } from "@/utils/operationId";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Input,
  Modal,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { useResponsive } from "@gouvfr-lasuite/ui-kit";
import { Item } from "@/features/drivers/types";
import { formatSize } from "@/features/explorer/utils/utils";
import { errorToString } from "@/features/api/APIError";
import { getMountExplorerMeta } from "@/features/mounts/utils/mountExplorerItems";
import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";
import {
  getResource,
  resolveLegacyMount,
  StoragePage,
  StorageResource,
  StorageSpace,
  storageRequest,
  resourceItem,
} from "./api";
import styles from "./StorageAdmin.module.scss";
import { resolveExplorerResource } from "./tree";

type Folder = { id: string; space: string; title: string };

export const StorageTransferModal = ({
  items,
  mode,
  onClose,
  initialDestination,
  selectionPaths,
}: {
  items: Item[];
  mode: "copy" | "move" | "archive" | "extract";
  onClose: () => void;
  initialDestination?: Item;
  selectionPaths?: string[];
}) => {
  const { t } = useTranslation();
  const { isDesktop } = useResponsive();
  const cache = useQueryClient();
  const [selectedTrail, setTrail] = useState<Folder[] | undefined>(
    initialDestination ? undefined : [],
  );
  const initial = useQuery({
    queryKey: ["storage", "transfer-destination", initialDestination?.id],
    queryFn: () => resolveExplorerResource(initialDestination!),
    enabled: Boolean(initialDestination) && selectedTrail === undefined,
  });
  const trail = selectedTrail ?? (initial.data ? [initial.data] : []);
  const [offset, setOffset] = useState(0);
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState<string[]>([]);
  const requestKeys = useRef(new Map<string, string>());
  const [error, setError] = useState("");
  const [name, setName] = useState(
    mode === "archive"
      ? defaultArchiveNameForItems(items)
      : mode === "extract"
        ? (items[0]?.filename || items[0]?.title || "archive").replace(
            /\.(zip|tar(\.(gz|bz2|xz))?|tgz|tbz2|txz)$/i,
            "",
          )
        : items[0]?.filename || items[0]?.title || "",
  );
  const current = trail.at(-1);
  const target = useQuery({
    queryKey: ["storage", "resource", current?.id, current?.space],
    queryFn: () => getResource(current!.id, current!.space),
    enabled: Boolean(current),
  });
  const sources = useQuery({
    queryKey: ["storage", "transfer-sources", items.map((item) => item.id)],
    queryFn: () =>
      Promise.all(
        items.map(async (item) => {
          const meta = getMountExplorerMeta(item);
          const source = meta
            ? await resolveLegacyMount(meta.mountId, meta.normalizedPath)
            : { id: item.originalId ?? item.id, space: undefined };
          return { source: source.id, source_space: source.space };
        }),
      ),
  });
  const impact = useQuery({
    queryKey: [
      "storage",
      "transfer-impact",
      sources.data,
      current?.id,
      current?.space,
      mode,
    ],
    enabled: Boolean(
      current &&
        sources.data &&
        (target.data?.abilities?.children_create ||
          target.data?.abilities?.upload),
    ),
    queryFn: () =>
      storageRequest<{
        files: number;
        bytes: number;
        global_additional_bytes: number;
        space_additional_bytes: number;
        attribution: string;
        sharing_allowed: boolean;
        public_links: number;
        shared_names: string[];
      }>("storage-transfers/impact/", {
        method: "POST",
        body: JSON.stringify({
          sources: sources.data,
          destination: current!.id,
          destination_space: current!.space,
          mode,
        }),
      }),
  });
  const folders = useQuery({
    queryKey: ["storage", "destinations", current?.id, current?.space, offset],
    queryFn: async () => {
      if (current) {
        const page = await storageRequest<StoragePage<StorageResource>>(
          `resources/${current.id}/children/`,
          {
            params: { space: current.space, kind: "folder", offset, limit: 50 },
          },
        );
        return {
          ...page,
          results: page.results.map(({ id, space, title }) => ({
            id,
            space,
            title,
          })),
        };
      }
      const page = await storageRequest<StoragePage<StorageSpace>>("spaces/", {
        params: { offset, limit: 50 },
      });
      return {
        ...page,
        results: page.results.flatMap((space) =>
          space.roots.map((root) => ({
            id: root.id,
            space: space.id,
            title:
              space.roots.length > 1
                ? `${space.name} — ${root.title}`
                : space.name,
          })),
        ),
      };
    },
    enabled: selectedTrail !== undefined || Boolean(initial.data),
  });
  const navigate = (next: Folder[]) => {
    setTrail(next);
    setOffset(0);
    setError("");
  };
  const submit = async () => {
    if (!current || pending || !sources.data || !impact.data) return;
    setPending(true);
    setError("");
    const completed = [...submitted];
    try {
      if (mode === "archive" || mode === "extract") {
        await storageRequest(`storage-transfers/${mode}/`, {
          method: "POST",
          body: JSON.stringify({
            sources: sources.data,
            destination: current.id,
            destination_space: current.space,
            mode,
            name,
            ...(selectionPaths ? { selection_paths: selectionPaths } : {}),
          }),
        });
        completed.push(...items.map((item) => item.id));
        setSubmitted([...completed]);
      }
      for (const [index, item] of items.entries()) {
        if (completed.includes(item.id)) continue;
        const intent = `${item.id}:${current.id}:${mode}`;
        const requestKey = requestKeys.current.get(intent) || uuid();
        requestKeys.current.set(intent, requestKey);
        await storageRequest("storage-transfers/", {
          method: "POST",
          body: JSON.stringify({
            ...sources.data[index],
            destination: current.id,
            destination_space: current.space,
            mode,
            request_key: requestKey,
            ...(mode === "copy" && items.length === 1 ? { name } : {}),
          }),
        });
        completed.push(item.id);
        setSubmitted([...completed]);
      }
      await cache.invalidateQueries({ queryKey: ["storage", "transfers"] });
      addToast(
        <ToasterItem>
          <Link href="/explorer/transfers">
            {t("storage.transfers.queued", { count: completed.length })}
          </Link>
        </ToasterItem>,
      );
      onClose();
    } catch (cause) {
      setError(errorToString(cause));
    } finally {
      setPending(false);
    }
  };
  const writable =
    target.data?.abilities?.children_create || target.data?.abilities?.upload;
  return (
    <Modal
      isOpen
      onClose={() => {
        if (!pending) onClose();
      }}
      size={isDesktop ? ModalSize.MEDIUM : ModalSize.FULL}
      title={t(`storage.transfers.pick_${mode}`)}
      aria-label={t(`storage.transfers.pick_${mode}`)}
      rightActions={
        <>
          <Button variant="tertiary" disabled={pending} onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            disabled={
              pending ||
              !writable ||
              (((mode === "copy" && items.length === 1) ||
                mode === "archive" ||
                mode === "extract") &&
                !name.trim()) ||
              target.isFetching ||
              impact.isPending ||
              impact.isFetching ||
              impact.isError ||
              sources.isError ||
              submitted.length === items.length
            }
            onClick={() => {
              void submit();
            }}
          >
            {t(`storage.transfers.submit_${mode}`)}
          </Button>
        </>
      }
    >
      <div className={styles.transferBody}>
        <p>
          {items.length === 1
            ? items[0].title
            : t("storage.transfers.selection", { count: items.length })}
        </p>
        {((mode === "copy" && items.length === 1) ||
          mode === "archive" ||
          mode === "extract") && (
          <Input
            label={t(
              mode === "archive"
                ? "explorer.actions.archive.zip.modal.archive_name_label"
                : mode === "extract"
                  ? "storage.transfers.extract_name"
                  : "storage.transfers.copy_name",
            )}
            value={name}
            maxLength={255}
            disabled={pending || submitted.length > 0}
            onChange={(event) => setName(event.target.value)}
          />
        )}
        {selectionPaths && (
          <p>
            {t("storage.transfers.extract_selection", {
              count: selectionPaths.length,
            })}
            : {selectionPaths.join(", ")}
          </p>
        )}
        <p>{t("storage.transfers.destination_rights")}</p>
        {current && impact.data && (
          <section aria-label={t("storage.transfers.impact_title")}>
            <p>
              {t(
                mode === "extract"
                  ? "storage.transfers.extract_source"
                  : "storage.transfers.impact_size",
                {
                  count: impact.data.files,
                  size: formatSize(impact.data.bytes),
                },
              )}
            </p>
            <p>
              {mode === "extract"
                ? t("storage.transfers.extract_estimate")
                : mode === "archive"
                  ? t("storage.transfers.archive_estimate")
                  : t("storage.transfers.impact_quotas", {
                      global: formatSize(impact.data.global_additional_bytes),
                      space: formatSize(impact.data.space_additional_bytes),
                    })}
            </p>
            <p>
              {t("storage.admin.attribution")}:{" "}
              {t(`storage.admin.rules.${impact.data.attribution}`)}
            </p>
            {mode === "move" && impact.data.public_links > 0 && (
              <p>
                {t("storage.transfers.impact_links", {
                  count: impact.data.public_links,
                })}{" "}
                {impact.data.shared_names.join(", ")}
              </p>
            )}
            {mode === "move" && !impact.data.sharing_allowed && (
              <p>{t("storage.transfers.impact_no_sharing")}</p>
            )}
            <p>{t("storage.transfers.impact_estimate")}</p>
          </section>
        )}
        {(sources.isError || impact.isError) && (
          <p role="alert">{errorToString(sources.error || impact.error)}</p>
        )}

        <nav
          aria-label={t("storage.transfers.destination")}
          className={styles.actions}
        >
          <Button
            variant="tertiary"
            disabled={pending || submitted.length > 0}
            onClick={() => navigate([])}
          >
            {t("storage.spaces")}
          </Button>
          {trail.map((folder, index) => (
            <Button
              key={`${folder.space}:${folder.id}`}
              variant="tertiary"
              disabled={pending || submitted.length > 0}
              onClick={() => navigate(trail.slice(0, index + 1))}
            >
              {folder.title}
            </Button>
          ))}
        </nav>
        {(error || folders.isError || target.isError || initial.isError) && (
          <p role="alert">{error || t("storage.load_error")}</p>
        )}
        {submitted.length > 0 && (
          <p role="status">
            {t("storage.transfers.queued", { count: submitted.length })}
          </p>
        )}
        {(folders.isFetching || initial.isFetching) && (
          <p role="status">{t("storage.loading")}</p>
        )}
        {!folders.isFetching && folders.data?.results.length === 0 && (
          <p>{t("storage.transfers.no_subfolders")}</p>
        )}
        {current && target.data && !writable && (
          <p>{t("storage.transfers.read_only")}</p>
        )}
        <ul>
          {folders.data?.results.map((folder) => (
            <li key={`${folder.space}:${folder.id}`}>
              <Button
                variant="tertiary"
                disabled={
                  pending ||
                  submitted.length > 0 ||
                  items.some((item) => item.id === folder.id)
                }
                onClick={() => navigate([...trail, folder])}
              >
                {folder.title}
              </Button>
            </li>
          ))}
        </ul>
        <div className={styles.actions}>
          <Button
            variant="tertiary"
            disabled={pending || offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 50))}
          >
            {t("storage.transfers.previous")}
          </Button>
          <Button
            variant="tertiary"
            disabled={pending || !folders.data?.next}
            onClick={() => setOffset(offset + 50)}
          >
            {t("storage.transfers.next")}
          </Button>
        </div>
      </div>
    </Modal>
  );
};

/** Resolve the viewer reference only when extraction is explicitly opened. */
export const UnifiedArchiveExtraction = ({
  id,
  mount,
  selectionPaths,
  onClose,
}: {
  id: string;
  mount?: { id: string; path: string };
  selectionPaths?: string[];
  onClose: () => void;
}) => {
  const { t } = useTranslation();
  const source = useQuery({
    queryKey: ["storage", "archive-source", id, mount?.id, mount?.path],
    queryFn: async () => {
      const reference = mount
        ? await resolveLegacyMount(mount.id, mount.path)
        : { id, space: undefined };
      return getResource(reference.id, reference.space);
    },
  });
  if (source.data)
    return (
      <StorageTransferModal
        items={[resourceItem(source.data)]}
        mode="extract"
        selectionPaths={selectionPaths}
        onClose={onClose}
      />
    );
  return (
    <Modal
      isOpen
      size={ModalSize.SMALL}
      onClose={onClose}
      title={t("storage.transfers.pick_extract")}
    >
      <p role={source.isError ? "alert" : "status"}>
        {source.isError ? errorToString(source.error) : t("storage.loading")}
      </p>
    </Modal>
  );
};
