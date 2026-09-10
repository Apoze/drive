import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Modal, ModalSize } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { errorToString } from "@/features/api/APIError";
import { writeTextToClipboard } from "@/hooks/useCopyToClipboard";
import { StoragePage, storageRequest } from "./api";
import styles from "./StorageAdmin.module.scss";

type PublicLink = { id: string; url: string; created_at: string };

export function ResourcePublicLinks({
  resourceId,
  space,
  canCreate = false,
  hideEmpty = false,
}: {
  resourceId: string;
  space?: string;
  canCreate?: boolean;
  hideEmpty?: boolean;
}) {
  const { t } = useTranslation();
  const [offset, setOffset] = useState(0);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const endpoint = `resources/${encodeURIComponent(resourceId)}/public-links/`;
  const links = useQuery({
    queryKey: ["resource-public-links", resourceId, space, offset],
    queryFn: () =>
      storageRequest<StoragePage<PublicLink>>(endpoint, {
        params: { ...(space ? { space } : {}), limit: 10, offset },
      }),
  });
  async function mutate(method: "POST" | "DELETE", link?: string) {
    setPending(true);
    setError("");
    setMessage("");
    try {
      await storageRequest(endpoint, {
        method,
        body: JSON.stringify(link ? { link } : {}),
        params: space ? { space } : {},
      });
      if (method === "DELETE" && links.data?.results.length === 1 && offset) {
        setOffset(Math.max(0, offset - 10));
      } else {
        await links.refetch();
      }
    } catch (cause) {
      setError(errorToString(cause));
    } finally {
      setPending(false);
    }
  }
  if (hideEmpty && !links.isError && !links.data?.count) return null;
  return (
    <section aria-label={t("storage.public_links.title")}>
      <h3>{t("storage.public_links.title")}</h3>
      <p>{t("storage.public_links.description")}</p>
      {(error || links.isError) && (
        <p role="alert">{error || errorToString(links.error)}</p>
      )}
      {links.isLoading && <p role="status">{t("storage.loading")}</p>}
      {message && <p role="status">{message}</p>}
      {links.data?.count === 0 && <p>{t("storage.public_links.empty")}</p>}
      {links.data?.results.map((link) => (
        <div key={link.id} className={styles.actions}>
          <a
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ overflowWrap: "anywhere", minWidth: 0 }}
          >
            {link.url}
          </a>
          <Button
            variant="tertiary"
            disabled={pending}
            onClick={() => {
              void writeTextToClipboard(link.url)
                .then(() => setMessage(t("storage.public_links.copied")))
                .catch((cause) => setError(errorToString(cause)));
            }}
          >
            {t("storage.public_links.copy")}
          </Button>
          <Button
            variant="tertiary"
            disabled={pending}
            onClick={() => {
              void mutate("DELETE", link.id);
            }}
          >
            {t("storage.public_links.revoke")}
          </Button>
        </div>
      ))}
      <div className={styles.actions}>
        {canCreate && (
          <Button
            disabled={pending}
            onClick={() => {
              void mutate("POST");
            }}
          >
            {t("storage.public_links.create")}
          </Button>
        )}
        {offset > 0 && (
          <Button
            variant="tertiary"
            disabled={pending}
            onClick={() => setOffset(offset - 10)}
          >
            {t("storage.public_links.previous")}
          </Button>
        )}
        {links.data?.next && (
          <Button
            variant="tertiary"
            disabled={pending}
            onClick={() => setOffset(offset + 10)}
          >
            {t("storage.public_links.next")}
          </Button>
        )}
      </div>
    </section>
  );
}

export function ResourcePublicLinksModal({
  title,
  onClose,
  ...props
}: {
  title: string;
  onClose: () => void;
  resourceId: string;
  space?: string;
  canCreate?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <Modal
      isOpen
      onClose={onClose}
      size={ModalSize.MEDIUM}
      title={title}
      aria-label={t("storage.public_links.title")}
    >
      <ResourcePublicLinks {...props} />
    </Modal>
  );
}
