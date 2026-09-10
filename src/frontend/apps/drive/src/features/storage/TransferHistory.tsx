import { Fragment, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { StoragePage, storageRequest } from "./api";
import styles from "./StorageAdmin.module.scss";

type Transfer = {
  id: string;
  mode: "move" | "copy";
  title: string;
  destination: string;
  state: "queued" | "running" | "cleanup" | "conflict" | "done" | "failed";
  reason: string;
  source_retained: boolean;
  progress?: { total: number; done: number } | null;
  can_retry: boolean;
  can_cancel: boolean;
  can_recover: boolean;
  can_accept: boolean;
};

type TransferAction = "cancel" | "retry" | "recover" | "accept";
type ActionsProps = {
  job: Transfer;
  pending?: string;
  act: (id: string, action: TransferAction) => Promise<void>;
};

const TransferActions = ({ job, pending, act }: ActionsProps) => {
  const { t } = useTranslation();
  return (
    <div className={styles.actions}>
      {(["cancel", "retry", "recover", "accept"] as const)
        .filter((action) => job[`can_${action}`])
        .map((action) => (
          <Button
            key={action}
            size="small"
            variant="secondary"
            disabled={pending !== undefined}
            onClick={() => {
              void act(job.id, action);
            }}
          >
            {t(`storage.transfers.${action}`)}
          </Button>
        ))}
    </div>
  );
};

type ManifestEntry = {
  id: string;
  title: string;
  done: boolean;
  retained_staging: number;
  transfer: Transfer | null;
};

const TransferDetails = ({ job, pending, act }: ActionsProps) => {
  const { t } = useTranslation();
  const [offset, setOffset] = useState(0);
  const entries = useQuery({
    queryKey: ["storage", "transfers", job.id, "entries", offset],
    queryFn: () =>
      storageRequest<StoragePage<ManifestEntry>>(
        `storage-transfers/${job.id}/entries/`,
        { params: { offset, limit: 20 } },
      ),
    refetchInterval: (query) =>
      ["queued", "running"].includes(job.state) ||
      query.state.data?.results.some(
        (entry) =>
          entry.transfer &&
          ["queued", "running"].includes(entry.transfer.state),
      )
        ? 5000
        : false,
  });
  return (
    <section aria-label={t("storage.transfers.details")}>
      <p>{t("storage.transfers.details_help")}</p>
      {entries.isPending && <p role="status">{t("storage.loading")}</p>}
      {entries.isError && <p role="alert">{t("storage.load_error")}</p>}
      <ul>
        {entries.data?.results.map((entry) => (
          <li key={entry.id}>
            <strong>{entry.title}</strong>
            {" — "}
            {t(
              `storage.transfers.states.${entry.transfer?.state ?? (entry.done ? "done" : "queued")}`,
            )}
            {entry.retained_staging > 0 && (
              <p>
                {t("storage.transfers.staging_retained", {
                  count: entry.retained_staging,
                })}
              </p>
            )}
            {entry.transfer && (
              <>
                {entry.transfer.reason && <p>{entry.transfer.reason}</p>}
                {entry.transfer.can_accept && (
                  <p>{t("storage.transfers.accept_description")}</p>
                )}
                <TransferActions
                  job={entry.transfer}
                  pending={pending}
                  act={act}
                />
              </>
            )}
          </li>
        ))}
      </ul>
      <div className={styles.actions}>
        <Button
          variant="tertiary"
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          {t("storage.transfers.previous")}
        </Button>
        <Button
          variant="tertiary"
          disabled={!entries.data?.next}
          onClick={() => setOffset(offset + 20)}
        >
          {t("storage.transfers.next")}
        </Button>
      </div>
    </section>
  );
};

export const TransferHistory = () => {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [pending, setPending] = useState<string>();
  const [error, setError] = useState(false);
  const [expanded, setExpanded] = useState<string>();
  const history = useQuery({
    queryKey: ["storage", "transfers", offset],
    queryFn: () =>
      storageRequest<StoragePage<Transfer>>("storage-transfers/", {
        params: { offset, limit: 50 },
      }),
    refetchInterval: (query) =>
      query.state.data?.results.some((job) =>
        ["queued", "running"].includes(job.state),
      )
        ? 5000
        : false,
  });
  const act = async (id: string, action: TransferAction) => {
    setPending(id);
    setError(false);
    try {
      await storageRequest(`storage-transfers/${id}/${action}/`, {
        method: "POST",
      });
      await cache.invalidateQueries({ queryKey: ["storage", "transfers"] });
    } catch {
      setError(true);
    } finally {
      setPending(undefined);
    }
  };
  return (
    <main className={`${styles.admin} ${styles.history}`}>
      <h1>{t("storage.transfers.title")}</h1>
      {(error || history.isError) && (
        <p role="alert">{t("storage.load_error")}</p>
      )}
      <Button
        variant="tertiary"
        disabled={history.isFetching}
        onClick={() => {
          void history.refetch();
        }}
      >
        {t("storage.transfers.refresh")}
      </Button>
      {history.isPending && <p role="status">{t("storage.loading")}</p>}
      {history.data && history.data.count === 0 && (
        <p>{t("storage.transfers.empty")}</p>
      )}
      {history.data && history.data.count > 0 && (
        <>
          <div className={styles.table}>
            <table>
              <caption>{t("storage.transfers.history")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("storage.transfers.file")}</th>
                  <th scope="col">{t("storage.transfers.destination")}</th>
                  <th scope="col">{t("storage.transfers.status")}</th>
                  <th scope="col">{t("storage.transfers.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {history.data.results.map((job) => (
                  <Fragment key={job.id}>
                    <tr>
                      <td data-label={t("storage.transfers.file")}>
                        {job.title || t("storage.transfers.transfer")}
                        <small>
                          {t(`storage.transfers.modes.${job.mode}`)}
                        </small>
                      </td>
                      <td data-label={t("storage.transfers.destination")}>
                        {job.destination}
                      </td>
                      <td data-label={t("storage.transfers.status")}>
                        <span>
                          {t(`storage.transfers.states.${job.state}`)}
                        </span>
                        {job.reason && <small>{job.reason}</small>}
                        {job.progress && (
                          <small>
                            {t("storage.transfers.progress", job.progress)}
                          </small>
                        )}
                        {job.can_accept && (
                          <small>
                            {t("storage.transfers.accept_description")}
                          </small>
                        )}
                        {job.source_retained && (
                          <small>{t("storage.transfers.retained")}</small>
                        )}
                      </td>
                      <td data-label={t("storage.transfers.actions")}>
                        <TransferActions
                          job={job}
                          pending={pending}
                          act={act}
                        />
                        {job.progress && (
                          <Button
                            size="small"
                            variant="tertiary"
                            aria-expanded={expanded === job.id}
                            onClick={() =>
                              setExpanded(
                                expanded === job.id ? undefined : job.id,
                              )
                            }
                          >
                            {t("storage.transfers.details")}
                          </Button>
                        )}
                      </td>
                    </tr>
                    {expanded === job.id && (
                      <tr>
                        <td colSpan={4}>
                          <TransferDetails
                            job={job}
                            pending={pending}
                            act={act}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <div className={styles.actions}>
            <Button
              variant="secondary"
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              {t("storage.transfers.previous")}
            </Button>
            <Button
              variant="secondary"
              disabled={!history.data.next}
              onClick={() => setOffset(offset + 50)}
            >
              {t("storage.transfers.next")}
            </Button>
          </div>
        </>
      )}
    </main>
  );
};
