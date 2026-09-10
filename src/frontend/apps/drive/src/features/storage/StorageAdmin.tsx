import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Input,
  Select,
  Modal,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { getOrigin } from "@/features/api/utils";
import {
  StoragePage,
  storageRequest,
  ConnectionChoice,
  Configuration,
  useStorageAdministration,
} from "./api";
import styles from "./StorageAdmin.module.scss";

type Connection = ConnectionChoice & {
  organization: string;
  enabled: boolean;
  managed: boolean;
  maintenance: boolean;
  attribution_pending: boolean;
  connection_status: string;
  connection_checked_at: string | null;
  inventory_completed_at: string | null;
  namespace: string;
  namespace_root: string;
  configuration: {
    provider?: string;
    params?: Record<string, string | number>;
    [key: string]: unknown;
  };
};
type Space = {
  id: string;
  name: string;
  backend: string;
  backend_name: string;
  family: string;
  root_path: string;
  root_item: string;
  owner: string | null;
  owner_label: string;
  enabled: boolean;
  attribute_to_creator: boolean;
  allow_sharing: boolean;
  usage: {
    used_bytes: number;
    reserved_bytes: number;
    limit_bytes: number | null;
    growth_blocked: boolean;
    policy_applied_at: string | null;
  } | null;
};
type Grant = {
  beneficiary: string;
  root_title: string;
  id: string;
  user: string | null;
  team: string;
  path: string;
  root_item: string | null;
  writable: boolean;
  shareable: boolean;
  manageable: boolean;
};
type Person = { id: string; email: string; full_name?: string };
const write = <T,>(path: string, body: unknown, method = "POST") =>
  storageRequest<T>(path, { method, body: JSON.stringify(body) });

const UserPicker = ({
  value,
  onChange,
  label,
  selectedLabel,
}: {
  value: string;
  selectedLabel?: string;
  onChange: (id: string) => void;
  label: string;
}) => {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const users = useQuery({
    queryKey: ["storage", "people", query],
    enabled: query.length >= 5,
    queryFn: () => storageRequest<Person[]>("users/", { params: { q: query } }),
  });
  return (
    <fieldset>
      <legend>{label}</legend>
      <Input
        label={t("storage.admin.search_person")}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
      <Button
        type="button"
        variant="tertiary"
        disabled={text.trim().length < 5}
        onClick={() => setQuery(text.trim())}
      >
        {t("storage.admin.search")}
      </Button>
      <Select
        label={label}
        value={value}
        onChange={(event) => onChange(String(event.target.value || ""))}
        options={[
          ...(value && !users.data?.some((person) => person.id === value)
            ? [{ value, label: selectedLabel || value }]
            : []),
          ...(users.data ?? []).map((person) => ({
            value: person.id,
            label: person.full_name
              ? `${person.full_name} (${person.email})`
              : person.email,
          })),
        ]}
      />
      {users.isError && <p role="alert">{t("storage.load_error")}</p>}
    </fieldset>
  );
};

export const StorageAdmin = () => {
  const { t } = useTranslation();
  const roles = useStorageAdministration();
  const cache = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [connectionOffset, setConnectionOffset] = useState(0);
  const [editor, setEditor] = useState<Connection | "new" | null>(null);
  const [spaceEditor, setSpaceEditor] = useState<Space | "new" | null>(null);
  const [accessSpace, setAccessSpace] = useState<Space | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [failure, setFailure] = useState(false);
  const openQuota = async (space: Space) => {
    setPending(true);
    setFailure(false);
    try {
      const result = await storageRequest<{ url: string }>(
        `storage-spaces-admin/${space.id}/quota-link/`,
      );
      window.location.assign(result.url);
    } catch {
      setFailure(true);
      setPending(false);
    }
  };
  const connections = useQuery({
    queryKey: ["storage", "connections", connectionOffset],
    enabled: Boolean(roles.data?.connections_manage),
    queryFn: () =>
      storageRequest<StoragePage<Connection>>("storage-connections/", {
        params: { offset: connectionOffset, limit: 50 },
      }),
    refetchInterval: (query) =>
      query.state.data?.results.some(
        (row) => row.connection_status === "checking",
      )
        ? 3000
        : false,
  });
  const spaces = useQuery({
    queryKey: ["storage", "managed-spaces", offset],
    enabled: Boolean(roles.data?.spaces_manage),
    queryFn: () =>
      storageRequest<StoragePage<Space>>("storage-spaces-admin/", {
        params: { offset, limit: 50 },
      }),
  });
  const refresh = async () => {
    await cache.invalidateQueries({ queryKey: ["storage"] });
  };
  const command = async (path: string, body: unknown = {}, method = "POST") => {
    setPending(true);
    setMessage("");
    setFailure(false);
    try {
      await write(path, body, method);
      await refresh();
      setMessage(t("storage.admin.saved"));
    } catch {
      setFailure(true);
      setMessage(t("storage.admin.failed"));
    } finally {
      setPending(false);
    }
  };
  if (roles.isPending) return <p role="status">{t("storage.loading")}</p>;
  if (!roles.data?.spaces_manage)
    return <p role="alert">{t("storage.admin.denied")}</p>;
  return (
    <main className={styles.admin}>
      <Link href="/explorer/items/my-files">{t("storage.spaces")}</Link>
      <h1>{t("storage.administration")}</h1>
      <p>{t("storage.admin.authorities")}</p>
      {roles.data.quota_url && (
        <a href={roles.data.quota_url} target="_blank" rel="noreferrer">
          {t("storage.admin.quotas")}
        </a>
      )}
      {message && <p role={failure ? "alert" : "status"}>{message}</p>}
      {roles.data.connections_manage && (
        <section aria-labelledby="storage-connections-heading">
          <h2 id="storage-connections-heading">
            {t("storage.admin.connections")}
          </h2>
          <Button onClick={() => setEditor("new")}>
            {t("storage.admin.add_connection")}
          </Button>
          <p>{t("storage.admin.connection_help")}</p>
          {connections.isError && <p role="alert">{t("storage.load_error")}</p>}
          <div className={styles.table}>
            <table>
              <thead>
                <tr>
                  {["name", "state", "last_check", "actions"].map((key) => (
                    <th key={key}>{t(`storage.admin.${key}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {connections.data?.results.map((connection) => (
                  <tr key={connection.id}>
                    <td>
                      {connection.name}
                      <small>
                        {connection.family === "s3"
                          ? "S3"
                          : connection.configuration.provider ||
                            "MountProvider"}{" "}
                        ·{" "}
                        {t(
                          connection.managed
                            ? "storage.admin.web_managed"
                            : "storage.admin.external_managed",
                        )}
                      </small>
                    </td>
                    <td>
                      {t(
                        `storage.admin.states.${connection.connection_status}`,
                      )}
                      <small>
                        {t(
                          connection.enabled
                            ? "storage.admin.enabled"
                            : "storage.admin.disabled",
                        )}
                        {connection.maintenance &&
                          ` · ${t("storage.admin.maintenance")}`}
                      </small>
                    </td>
                    <td>
                      {connection.connection_checked_at
                        ? new Date(
                            connection.connection_checked_at,
                          ).toLocaleString()
                        : "—"}
                    </td>
                    <td>
                      <div className={styles.actions}>
                        <Button
                          size="small"
                          variant="tertiary"
                          onClick={() => setEditor(connection)}
                        >
                          {t("storage.admin.edit")}
                        </Button>
                        <Button
                          size="small"
                          variant="tertiary"
                          disabled={
                            pending ||
                            connection.connection_status === "checking"
                          }
                          onClick={() =>
                            void command(
                              `storage-connections/${connection.id}/test/`,
                            )
                          }
                        >
                          {t("storage.admin.test")}
                        </Button>
                        <Button
                          size="small"
                          variant="tertiary"
                          disabled={
                            pending ||
                            (!connection.enabled &&
                              connection.managed &&
                              connection.connection_status !== "ready")
                          }
                          onClick={() =>
                            void command(
                              `storage-connections/${connection.id}/`,
                              { enabled: !connection.enabled },
                              "PATCH",
                            )
                          }
                        >
                          {t(
                            connection.enabled
                              ? "storage.admin.disable"
                              : "storage.admin.enable",
                          )}
                        </Button>
                        {connection.family === "mount" && (
                          <Button
                            size="small"
                            variant="tertiary"
                            disabled={pending}
                            onClick={() =>
                              void command(
                                `storage-connections/${connection.id}/inventory/`,
                              )
                            }
                          >
                            {t("storage.admin.inventory")}
                          </Button>
                        )}
                        <Button
                          size="small"
                          variant="tertiary"
                          disabled={pending}
                          onClick={() =>
                            void command(
                              `storage-connections/${connection.id}/${connection.maintenance ? "reclassify" : "maintenance"}/`,
                            )
                          }
                        >
                          {t(
                            connection.maintenance
                              ? "storage.admin.reclassify"
                              : "storage.admin.maintenance",
                          )}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager
            offset={connectionOffset}
            next={Boolean(connections.data?.next)}
            onChange={setConnectionOffset}
          />
        </section>
      )}
      {roles.data.connections_manage && (
        <>
          <AdministrativeOperations />
          <RetainedVersions />
        </>
      )}
      <section aria-labelledby="storage-spaces-heading">
        <h2 id="storage-spaces-heading">{t("storage.spaces")}</h2>
        {roles.data.spaces_create && (
          <Button onClick={() => setSpaceEditor("new")}>
            {t("storage.admin.add_space")}
          </Button>
        )}
        {spaces.isError && <p role="alert">{t("storage.load_error")}</p>}
        <div className={styles.table}>
          <table>
            <thead>
              <tr>
                {["name", "usage", "actions"].map((key) => (
                  <th key={key}>{t(`storage.admin.${key}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {spaces.data?.results.map((space) => (
                <tr key={space.id}>
                  <td>
                    {space.name}
                    <small>
                      {space.backend_name} ·{" "}
                      {t(
                        space.enabled
                          ? "storage.admin.enabled"
                          : "storage.admin.disabled",
                      )}
                    </small>
                  </td>
                  <td>
                    {space.usage ? (
                      <>
                        {t("storage.admin.bytes", {
                          count: space.usage.used_bytes,
                        })}
                        <small>
                          {t("storage.admin.reserved", {
                            count: space.usage.reserved_bytes,
                          })}{" "}
                          ·{" "}
                          {space.usage.limit_bytes === null
                            ? t("storage.admin.unlimited")
                            : t("storage.admin.limit", {
                                count: space.usage.limit_bytes,
                              })}
                        </small>
                        <small>
                          {space.usage.policy_applied_at
                            ? new Date(
                                space.usage.policy_applied_at,
                              ).toLocaleString()
                            : t("storage.admin.awaiting_policy")}
                          {space.usage.growth_blocked &&
                            ` · ${t("storage.admin.growth_blocked")}`}
                        </small>
                      </>
                    ) : (
                      t("storage.admin.awaiting_inventory")
                    )}
                  </td>
                  <td>
                    <div className={styles.actions}>
                      <Button
                        size="small"
                        variant="tertiary"
                        onClick={() => setSpaceEditor(space)}
                      >
                        {t("storage.admin.edit")}
                      </Button>
                      {roles.data.spaces_create && roles.data.quota_url && (
                        <Button
                          size="small"
                          variant="tertiary"
                          disabled={pending}
                          onClick={() => void openQuota(space)}
                        >
                          {t("storage.admin.quotas")}
                        </Button>
                      )}
                      <Button
                        size="small"
                        variant="tertiary"
                        onClick={() => setAccessSpace(space)}
                      >
                        {t("storage.admin.access")}
                      </Button>
                      {roles.data.connections_manage &&
                        space.family === "mount" && (
                          <Button
                            size="small"
                            variant="tertiary"
                            disabled={pending}
                            onClick={() =>
                              void command(
                                `storage-spaces-admin/${space.id}/initialize-root/`,
                              )
                            }
                          >
                            {t("storage.admin.initialize_root")}
                          </Button>
                        )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pager
          offset={offset}
          next={Boolean(spaces.data?.next)}
          onChange={setOffset}
        />
      </section>
      {editor && (
        <ConnectionEditor
          connection={editor === "new" ? undefined : editor}
          configuration={roles.data}
          onClose={() => setEditor(null)}
          onSaved={refresh}
        />
      )}
      {spaceEditor && (
        <SpaceEditor
          space={spaceEditor === "new" ? undefined : spaceEditor}
          configuration={roles.data}
          onClose={() => setSpaceEditor(null)}
          onSaved={refresh}
        />
      )}
      {accessSpace && (
        <AccessEditor
          space={accessSpace}
          canDelegate={roles.data.spaces_create}
          onClose={() => setAccessSpace(null)}
          onSaved={refresh}
        />
      )}
    </main>
  );
};

const Pager = ({
  offset,
  next,
  onChange,
}: {
  offset: number;
  next: boolean;
  onChange: (value: number) => void;
}) => {
  const { t } = useTranslation();
  if (!offset && !next) return null;
  return (
    <div className={styles.actions}>
      <Button
        variant="tertiary"
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - 50))}
      >
        {t("storage.admin.previous")}
      </Button>
      <Button
        variant="tertiary"
        disabled={!next}
        onClick={() => onChange(offset + 50)}
      >
        {t("storage.admin.next")}
      </Button>
    </div>
  );
};

type EditorProps = {
  configuration: Configuration;
  onClose: () => void;
  onSaved: () => Promise<void>;
};
const ConnectionEditor = ({
  connection,
  configuration,
  onClose,
  onSaved,
}: EditorProps & { connection?: Connection }) => {
  const { t } = useTranslation();
  const [name, setName] = useState(connection?.name || "");
  const [organization, setOrganization] = useState(
    connection?.organization || configuration.organization,
  );
  const [kind, setKind] = useState(
    connection?.family === "s3"
      ? "s3"
      : connection?.configuration.provider || "s3",
  );
  const [fields, setFields] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      Object.entries(
        connection?.family === "mount"
          ? connection.configuration.params || {}
          : connection?.configuration || {},
      )
        .filter(
          ([, value]) => typeof value === "string" || typeof value === "number",
        )
        .map(([key, value]) => [key, String(value)]),
    ),
  );
  const [secret, setSecret] = useState("");
  const [accessKey, setAccessKey] = useState("");
  const [alias, setAlias] = useState("");
  const [namespaceRoot, setNamespaceRoot] = useState(
    connection?.namespace_root || "/",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const external = Boolean(connection && !connection.managed);
  const input = (key: string, required = false, type = "text") => (
    <Input
      key={key}
      label={t(`storage.admin.fields.${key}`)}
      type={type}
      required={required}
      disabled={external}
      value={fields[key] || ""}
      onChange={(event) => setFields({ ...fields, [key]: event.target.value })}
    />
  );
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(false);
    const values = Object.fromEntries(
      Object.entries(fields).filter(([, value]) => value !== ""),
    );
    const config =
      kind === "s3"
        ? values
        : {
            provider: kind,
            params: {
              ...Object.fromEntries(
                Object.entries(connection?.configuration.params || {}).filter(
                  ([key]) => !(key in fields),
                ),
              ),
              ...values,
              ...(values.port ? { port: Number(values.port) } : {}),
            },
          };
    try {
      await write(
        `storage-connections/${connection ? `${connection.id}/` : ""}`,
        external
          ? { name }
          : {
              name,
              organization,
              family: kind === "s3" ? "s3" : "mount",
              configuration: config,
              ...(!connection
                ? {
                    namespace_root: namespaceRoot,
                    ...(alias ? { alias_of: alias } : {}),
                  }
                : {}),
              ...(secret
                ? {
                    credentials:
                      kind === "s3"
                        ? { access_key: accessKey, secret_key: secret }
                        : { password: secret },
                  }
                : {}),
            },
        connection ? "PATCH" : "POST",
      );
      setSecret("");
      setAccessKey("");
      await onSaved();
      onClose();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      isOpen
      onClose={onClose}
      size={ModalSize.MEDIUM}
      title={t(
        connection
          ? "storage.admin.edit_connection"
          : "storage.admin.add_connection",
      )}
      closeOnEsc
      closeOnClickOutside={false}
    >
      <form className={styles.form} onSubmit={submit}>
        <Input
          label={t("storage.admin.name")}
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <Input
          label={t("storage.admin.organization")}
          required
          disabled={external || Boolean(connection)}
          value={organization}
          onChange={(event) => setOrganization(event.target.value)}
        />
        {!connection && (
          <>
            <Select
              label={t("storage.admin.alias")}
              value={alias}
              options={configuration.connections
                .filter(
                  (row) => row.family === (kind === "s3" ? "s3" : "mount"),
                )
                .map((row) => ({ value: row.id, label: row.name }))}
              onChange={(event) => setAlias(String(event.target.value || ""))}
            />
            {alias && (
              <Input
                label={t("storage.admin.namespace_root")}
                value={namespaceRoot}
                onChange={(event) => setNamespaceRoot(event.target.value)}
              />
            )}
          </>
        )}
        <Select
          label={t("storage.admin.type")}
          value={kind}
          disabled={Boolean(connection)}
          clearable={false}
          options={[
            { value: "s3", label: "S3" },
            { value: "smb", label: "SMB" },
            { value: "localfs", label: t("storage.admin.localfs") },
          ]}
          onChange={(event) => {
            setKind(String(event.target.value));
            setFields({});
          }}
        />
        {kind === "s3" ? (
          <>
            {input("endpoint_url", true, "url")}
            {input("bucket_name", true)}
            {input("region_name")}
            {input("prefix")}
            <Select
              label={t("storage.admin.fields.addressing_style")}
              value={fields.addressing_style || "path"}
              disabled={external}
              clearable={false}
              options={["path", "virtual", "auto"].map((value) => ({
                value,
                label: value,
              }))}
              onChange={(event) =>
                setFields({
                  ...fields,
                  addressing_style: String(event.target.value),
                })
              }
            />
            <Select
              label={t("storage.admin.fields.tls_ca")}
              value={fields.tls_ca || ""}
              disabled={external}
              options={configuration.certificate_authorities.map((value) => ({
                value,
                label: value,
              }))}
              onChange={(event) =>
                setFields({
                  ...fields,
                  tls_ca: String(event.target.value || ""),
                })
              }
            />
          </>
        ) : kind === "smb" ? (
          <>
            {input("server", true)}
            {input("share", true)}
            {input("username", true)}
            {input("port", false, "number")}
            {input("domain")}
            {input("base_path")}
          </>
        ) : (
          input("root_dir", true)
        )}
        {!external && kind !== "localfs" && (
          <>
            <p>{t("storage.admin.secret_help")}</p>
            {kind === "s3" && (
              <Input
                label={t("storage.admin.access_key")}
                value={accessKey}
                autoComplete="off"
                required={Boolean(secret)}
                onChange={(event) => setAccessKey(event.target.value)}
              />
            )}
            <Input
              label={t("storage.admin.secret")}
              type="password"
              autoComplete="new-password"
              required={!connection}
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
            />
          </>
        )}
        {error && <p role="alert">{t("storage.admin.failed")}</p>}
        <Button type="submit" disabled={busy}>
          {t("common.save")}
        </Button>
      </form>
    </Modal>
  );
};

const SpaceEditor = ({
  space,
  configuration,
  onClose,
  onSaved,
}: EditorProps & { space?: Space }) => {
  const { t } = useTranslation();
  const [name, setName] = useState(space?.name || "");
  const [backend, setBackend] = useState(space?.backend || "");
  const [path, setPath] = useState(space?.root_path || "/");
  const [owner, setOwner] = useState(space?.owner || "");
  const [rule, setRule] = useState(
    space?.attribute_to_creator ? "creator" : space?.owner ? "owner" : "common",
  );
  const [enabled, setEnabled] = useState(space?.enabled ?? false);
  const [sharing, setSharing] = useState(space?.allow_sharing ?? true);
  const [root, setRoot] = useState({ id: "", title: "" });
  const [parents, setParents] = useState<(typeof root)[]>([]);
  const [folderOffset, setFolderOffset] = useState(0);
  const family =
    space?.family ||
    configuration.connections.find((row) => row.id === backend)?.family;
  const roots = useQuery({
    queryKey: ["storage", "root-folders", backend, root.id, folderOffset],
    enabled: !space && family === "s3",
    queryFn: () =>
      storageRequest<
        StoragePage<{ id: string; title: string }> & {
          allocated: boolean;
          overlaps: { id: string; name: string }[];
        }
      >("storage-spaces-admin/root-folders/", {
        params: {
          backend,
          ...(root.id ? { parent: root.id } : {}),
          offset: folderOffset,
          limit: 50,
        },
      }),
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const impact = useQuery({
    queryKey: ["storage", "impact", space?.id],
    enabled: Boolean(space),
    queryFn: () =>
      storageRequest<{
        overlaps: { id: string; name: string }[];
        active_operations: number;
      }>(`storage-spaces-admin/${space!.id}/impact/`),
  });
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(false);
    try {
      await write(
        `storage-spaces-admin/${space ? `${space.id}/` : ""}`,
        configuration.spaces_create
          ? {
              name,
              backend,
              root_path: path,
              ...(!space && family === "s3" && root.id
                ? { root_item: root.id }
                : {}),
              owner: rule === "owner" ? owner : null,
              attribute_to_creator: rule === "creator",
              enabled,
              allow_sharing: sharing,
            }
          : { name },
        space ? "PATCH" : "POST",
      );
      await onSaved();
      onClose();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      isOpen
      onClose={onClose}
      size={ModalSize.MEDIUM}
      title={t("storage.admin.space")}
      closeOnEsc
      closeOnClickOutside={false}
    >
      <form className={styles.form} onSubmit={submit}>
        <Input
          label={t("storage.admin.name")}
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        {configuration.spaces_create && (
          <>
            <Select
              label={t("storage.admin.connection")}
              value={backend}
              disabled={Boolean(space)}
              clearable={false}
              options={configuration.connections.map((value) => ({
                value: value.id,
                label: value.name,
              }))}
              onChange={(event) => {
                setBackend(String(event.target.value || ""));
                setRoot({ id: "", title: "" });
                setParents([]);
                setFolderOffset(0);
              }}
            />
            {(space?.family ||
              configuration.connections.find((row) => row.id === backend)
                ?.family) === "mount" && (
              <Input
                label={t("storage.admin.root")}
                required
                value={path}
                onChange={(event) => setPath(event.target.value)}
              />
            )}
            {!space && family === "s3" && (
              <fieldset>
                <legend>{t("storage.admin.logical_root")}</legend>
                <Button
                  variant="tertiary"
                  onClick={() => {
                    setRoot({ id: "", title: "" });
                    setParents([]);
                    setFolderOffset(0);
                  }}
                >
                  {t("storage.admin.new_root")}
                </Button>
                <Select
                  label={t("storage.admin.folder")}
                  value=""
                  options={(roots.data?.results ?? []).map((row) => ({
                    value: row.id,
                    label: row.title,
                  }))}
                  onChange={(event) => {
                    const next = roots.data?.results.find(
                      (row) => row.id === event.target.value,
                    );
                    if (next) {
                      setParents([...parents, root]);
                      setRoot(next);
                      setFolderOffset(0);
                    }
                  }}
                />
                <Pager
                  offset={folderOffset}
                  next={Boolean(roots.data?.next)}
                  onChange={setFolderOffset}
                />
                <Button
                  variant="tertiary"
                  disabled={!parents.length}
                  onClick={() => {
                    const previous = parents[parents.length - 1];
                    if (previous) {
                      setRoot(previous);
                      setParents(parents.slice(0, -1));
                      setFolderOffset(0);
                    }
                  }}
                >
                  {t("storage.admin.parent_folder")}
                </Button>
                <p>{root.title || t("storage.admin.new_root")}</p>
                {!!root.id && <p>{t("storage.admin.existing_root_help")}</p>}
                {roots.data?.allocated && (
                  <p role="status">{t("storage.admin.root_allocated")}</p>
                )}
                {!!roots.data?.overlaps.length && (
                  <p>
                    {t("storage.admin.overlapping_spaces")}:{" "}
                    {roots.data.overlaps.map((row) => row.name).join(", ")}
                  </p>
                )}
                {roots.isError && (
                  <p role="alert">{t("storage.admin.failed")}</p>
                )}
              </fieldset>
            )}
            <Select
              label={t("storage.admin.attribution")}
              value={rule}
              clearable={false}
              options={["common", "owner", "creator"].map((value) => ({
                value,
                label: t(`storage.admin.rules.${value}`),
              }))}
              onChange={(event) => setRule(String(event.target.value))}
            />
            {rule === "owner" && (
              <UserPicker
                value={owner}
                selectedLabel={
                  owner === space?.owner ? space.owner_label : undefined
                }
                onChange={setOwner}
                label={t("storage.admin.owner")}
              />
            )}
            <label>
              <input
                type="checkbox"
                checked={enabled}
                onChange={(event) => setEnabled(event.target.checked)}
              />{" "}
              {t("storage.admin.enabled")}
            </label>
            <label>
              <input
                type="checkbox"
                checked={sharing}
                onChange={(event) => setSharing(event.target.checked)}
              />{" "}
              {t("storage.admin.allow_sharing")}
            </label>
          </>
        )}
        <p>{t("storage.admin.space_help")}</p>
        {impact.data && (
          <p>
            {t("storage.admin.impact", {
              count: impact.data.active_operations,
            })}{" "}
            {impact.data.overlaps.map((row) => row.name).join(", ")}
          </p>
        )}
        {error && <p role="alert">{t("storage.admin.failed")}</p>}
        <Button
          type="submit"
          disabled={
            busy ||
            !backend ||
            (rule === "owner" && !owner) ||
            (!space &&
              family === "s3" &&
              !!root.id &&
              (roots.isFetching || roots.isError || roots.data?.allocated))
          }
        >
          {t("common.save")}
        </Button>
      </form>
    </Modal>
  );
};

const GroupPicker = ({
  spaceId,
  value,
  onChange,
}: {
  spaceId: string;
  value: string;
  onChange: (id: string) => void;
}) => {
  const { t } = useTranslation();
  const roles = useStorageAdministration();
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedName, setSelectedName] = useState("");
  const groups = useQuery({
    queryKey: ["storage", "groups", spaceId, query, offset],
    queryFn: () =>
      storageRequest<StoragePage<{ id: string; name: string }>>(
        `storage-spaces-admin/${spaceId}/groups/`,
        { params: { q: query, offset, limit: 50 } },
      ),
  });
  return (
    <fieldset>
      <legend>{t("storage.admin.team")}</legend>
      <Input
        label={t("storage.admin.search_group")}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
      <Button
        type="button"
        variant="tertiary"
        onClick={() => {
          setOffset(0);
          setQuery(text.trim());
        }}
      >
        {t("storage.admin.search")}
      </Button>
      <Select
        label={t("storage.admin.team")}
        value={value}
        onChange={(event) => {
          const id = String(event.target.value || "");
          setSelectedName(
            groups.data?.results.find((group) => group.id === id)?.name || "",
          );
          onChange(id);
        }}
        options={[
          ...(value && !groups.data?.results.some((group) => group.id === value)
            ? [{ value, label: selectedName || value }]
            : []),
          ...(groups.data?.results ?? []).map((group) => ({
            value: group.id,
            label: group.name,
          })),
        ]}
      />
      <Pager
        offset={offset}
        next={Boolean(groups.data?.next)}
        onChange={setOffset}
      />
      <p>{t("storage.admin.group_help")}</p>
      {roles.data?.connections_manage && (
        <a
          href={`${getOrigin()}/admin/auth/group/`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t("storage.admin.manage_groups")}
        </a>
      )}
      {groups.isError && <p role="alert">{t("storage.load_error")}</p>}
    </fieldset>
  );
};

const AccessEditor = ({
  space,
  canDelegate,
  onClose,
  onSaved,
}: {
  space: Space;
  canDelegate: boolean;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) => {
  const { t } = useTranslation();
  const [user, setUser] = useState("");
  const [team, setTeam] = useState("");
  const [kind, setKind] = useState("user");
  const [path, setPath] = useState("/");
  const [root, setRoot] = useState("");
  const [rootTitle, setRootTitle] = useState("");
  const [folderOffset, setFolderOffset] = useState(0);
  const [parents, setParents] = useState<{ id: string; title: string }[]>([]);
  const [writable, setWritable] = useState(false);
  const [shareable, setShareable] = useState(false);
  const [manageable, setManageable] = useState(false);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const grants = useQuery({
    queryKey: ["storage", "grants", space.id, offset],
    queryFn: () =>
      storageRequest<StoragePage<Grant>>(
        `storage-spaces-admin/${space.id}/grants/`,
        { params: { offset, limit: 50 } },
      ),
  });
  const folders = useQuery({
    queryKey: ["storage", "grant-folders", space.id, root, folderOffset],
    enabled: space.family === "s3",
    queryFn: () =>
      storageRequest<StoragePage<{ id: string; title: string }>>(
        `storage-spaces-admin/${space.id}/folders/`,
        {
          params: {
            ...(root ? { parent: root } : {}),
            offset: folderOffset,
            limit: 50,
          },
        },
      ),
  });
  const change = async (body: unknown, method = "POST") => {
    setBusy(true);
    setError(false);
    try {
      await write(`storage-spaces-admin/${space.id}/grants/`, body, method);
      await onSaved();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      isOpen
      onClose={onClose}
      size={ModalSize.MEDIUM}
      title={`${t("storage.admin.access")} — ${space.name}`}
      closeOnEsc
      closeOnClickOutside={false}
    >
      <div className={styles.form}>
        <p>{t("storage.admin.access_help")}</p>
        {grants.data?.results.map((grant) => (
          <div key={grant.id} className={styles.actions}>
            <span>
              {grant.beneficiary} · {grant.root_title || grant.path} ·{" "}
              {t(grant.writable ? "storage.admin.write" : "storage.admin.read")}
            </span>
            <Button
              variant="tertiary"
              disabled={busy}
              onClick={() => void change({ id: grant.id }, "DELETE")}
            >
              {t("storage.admin.revoke")}
            </Button>
          </div>
        ))}
        <Pager
          offset={offset}
          next={Boolean(grants.data?.next)}
          onChange={setOffset}
        />
        <Select
          label={t("storage.admin.beneficiary")}
          value={kind}
          clearable={false}
          options={["user", "team"].map((value) => ({
            value,
            label: t(`storage.admin.${value}`),
          }))}
          onChange={(event) => setKind(String(event.target.value))}
        />
        {kind === "user" ? (
          <UserPicker
            value={user}
            onChange={setUser}
            label={t("storage.admin.user")}
          />
        ) : (
          <GroupPicker spaceId={space.id} value={team} onChange={setTeam} />
        )}
        {space.family === "mount" ? (
          <Input
            label={t("storage.admin.subfolder")}
            value={path}
            onChange={(event) => {
              setPath(event.target.value);
              if (event.target.value !== "/") setManageable(false);
            }}
          />
        ) : (
          <fieldset>
            <legend>{t("storage.admin.subfolder")}</legend>
            <Button
              variant="tertiary"
              onClick={() => {
                setRoot("");
                setRootTitle("");
                setFolderOffset(0);
                setParents([]);
              }}
            >
              {t("storage.admin.entire_space")}
            </Button>
            <Select
              label={t("storage.admin.folder")}
              value=""
              options={(folders.data?.results ?? []).map((row) => ({
                value: row.id,
                label: row.title,
              }))}
              onChange={(event) => {
                if (event.target.value) {
                  setParents([...parents, { id: root, title: rootTitle }]);
                  setFolderOffset(0);
                  setManageable(false);
                  setRoot(String(event.target.value));
                  setRootTitle(
                    folders.data?.results.find(
                      (row) => row.id === event.target.value,
                    )?.title || "",
                  );
                }
              }}
            />
            <Pager
              offset={folderOffset}
              next={Boolean(folders.data?.next)}
              onChange={setFolderOffset}
            />
            <Button
              variant="tertiary"
              disabled={!parents.length}
              onClick={() => {
                const previous = parents[parents.length - 1];
                if (!previous) return;
                setRoot(previous.id);
                setRootTitle(previous.title);
                setFolderOffset(0);
                setParents(parents.slice(0, -1));
              }}
            >
              {t("storage.admin.parent_folder")}
            </Button>
            <p>{rootTitle || t("storage.admin.entire_space")}</p>
          </fieldset>
        )}
        <label>
          <input
            type="checkbox"
            checked={writable}
            onChange={(event) => setWritable(event.target.checked)}
          />{" "}
          {t("storage.admin.write")}
        </label>
        <label>
          <input
            type="checkbox"
            checked={shareable}
            onChange={(event) => setShareable(event.target.checked)}
          />{" "}
          {t("storage.admin.share")}
        </label>
        {canDelegate && (
          <label>
            <input
              type="checkbox"
              checked={manageable}
              disabled={Boolean(root) || path !== "/"}
              onChange={(event) => setManageable(event.target.checked)}
            />{" "}
            {t("storage.admin.manage")}
          </label>
        )}
        {(error || grants.isError || folders.isError) && (
          <p role="alert">{t("storage.admin.failed")}</p>
        )}
        <Button
          disabled={busy || (kind === "user" ? !user : !team.trim())}
          onClick={() =>
            void change({
              user: kind === "user" ? user : null,
              team: kind === "team" ? team.trim() : "",
              path,
              root_item: root || null,
              writable,
              shareable,
              manageable: manageable && !root && path === "/",
            })
          }
        >
          {t("storage.admin.grant")}
        </Button>
      </div>
    </Modal>
  );
};

const AdministrativeOperations = () => {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  type Job = {
    id: string;
    kind: string;
    state: string;
    connection: string;
    space: string;
    reason: string;
    can_retry: boolean;
    can_cancel: boolean;
  };
  const jobs = useQuery({
    queryKey: ["storage", "admin-jobs", offset],
    queryFn: () =>
      storageRequest<StoragePage<Job>>("storage-administration-jobs/", {
        params: { offset, limit: 50 },
      }),
    refetchInterval: (query) =>
      query.state.data?.results.some((job) =>
        ["queued", "running"].includes(job.state),
      )
        ? 3000
        : false,
  });
  const completed = jobs.data?.results
    .filter((job) => !["queued", "running"].includes(job.state))
    .map((job) => `${job.id}:${job.state}`)
    .join(",");
  useEffect(() => {
    if (completed) {
      for (const key of [
        "connections",
        "managed-spaces",
        "spaces",
        "retained-versions",
      ]) {
        void cache.invalidateQueries({ queryKey: ["storage", key] });
      }
    }
  }, [cache, completed]);
  const act = async (id: string, action: "retry" | "cancel") => {
    setPending(true);
    setError(false);
    try {
      await storageRequest(`storage-administration-jobs/${id}/${action}/`, {
        method: "POST",
      });
      await cache.invalidateQueries({ queryKey: ["storage"] });
    } catch {
      setError(true);
    } finally {
      setPending(false);
    }
  };
  return (
    <section aria-labelledby="storage-operations-heading">
      <h2 id="storage-operations-heading">{t("storage.admin.operations")}</h2>
      <Button
        variant="tertiary"
        disabled={jobs.isFetching}
        onClick={() => void jobs.refetch()}
      >
        {t("storage.transfers.refresh")}
      </Button>
      {(error || jobs.isError) && (
        <p role="alert">{t("storage.admin.failed")}</p>
      )}
      {jobs.isPending && <p role="status">{t("storage.loading")}</p>}
      {jobs.data?.results.map((job) => (
        <div key={job.id} className={styles.actions}>
          <span>
            {job.connection}
            {job.space && ` — ${job.space}`} ·{" "}
            {t(`storage.admin.operation_kinds.${job.kind}`)} ·{" "}
            {t(`storage.transfers.states.${job.state}`)}
            {job.reason && <small>{job.reason}</small>}
          </span>
          {(["retry", "cancel"] as const)
            .filter((action) => job[`can_${action}`])
            .map((action) => (
              <Button
                key={action}
                size="small"
                variant="tertiary"
                disabled={pending}
                onClick={() => void act(job.id, action)}
              >
                {t(`storage.transfers.${action}`)}
              </Button>
            ))}
        </div>
      ))}
      <Pager
        offset={offset}
        next={Boolean(jobs.data?.next)}
        onChange={setOffset}
      />
    </section>
  );
};

const RetainedVersions = () => {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [spaceOffset, setSpaceOffset] = useState(0);
  const [selected, setSelected] = useState<{ id: string; title: string }>();
  const [space, setSpace] = useState("");
  const [path, setPath] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const versions = useQuery({
    queryKey: ["storage", "retained-versions", offset],
    queryFn: () =>
      storageRequest<
        StoragePage<{ id: string; title: string; retained_at: string }>
      >("storage-administration-jobs/retained-versions/", {
        params: { offset, limit: 50 },
      }),
  });
  const spaces = useQuery({
    queryKey: ["storage", "restore-spaces", spaceOffset],
    enabled: Boolean(selected),
    queryFn: () =>
      storageRequest<StoragePage<Space>>("storage-spaces-admin/", {
        params: { offset: spaceOffset, limit: 50 },
      }),
  });
  const restore = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setPending(true);
    setError(false);
    try {
      await write("storage-administration-jobs/restore/", {
        version: selected.id,
        space,
        path,
      });
      setSelected(undefined);
      await cache.invalidateQueries({ queryKey: ["storage"] });
    } catch {
      setError(true);
    } finally {
      setPending(false);
    }
  };
  return (
    <section aria-labelledby="storage-retained-heading">
      <h2 id="storage-retained-heading">
        {t("storage.admin.retained_versions")}
      </h2>
      {versions.isError && <p role="alert">{t("storage.load_error")}</p>}
      {versions.isPending && <p role="status">{t("storage.loading")}</p>}
      {versions.data?.count === 0 && (
        <p>{t("storage.admin.no_retained_versions")}</p>
      )}
      {versions.data?.results.map((version) => (
        <div key={version.id} className={styles.actions}>
          <span>
            {version.title} · {new Date(version.retained_at).toLocaleString()}
          </span>
          <Button
            size="small"
            variant="tertiary"
            onClick={() => {
              setSelected(version);
              setPath(`/restored-${version.title}`);
              setSpace("");
              setError(false);
            }}
          >
            {t("storage.admin.restore")}
          </Button>
        </div>
      ))}
      <Pager
        offset={offset}
        next={Boolean(versions.data?.next)}
        onChange={setOffset}
      />
      {selected && (
        <Modal
          isOpen
          title={t("storage.admin.restore")}
          size={ModalSize.MEDIUM}
          onClose={() => {
            if (!pending) setSelected(undefined);
          }}
          closeOnEsc={!pending}
          closeOnClickOutside={false}
        >
          <form className={styles.form} onSubmit={restore}>
            <p>{t("storage.admin.restore_help")}</p>
            <Select
              label={t("storage.admin.space")}
              value={space}
              clearable={false}
              options={(spaces.data?.results || [])
                .filter((row) => row.family === "mount" && row.enabled)
                .map((row) => ({ value: row.id, label: row.name }))}
              onChange={(event) => setSpace(String(event.target.value || ""))}
            />
            <Pager
              offset={spaceOffset}
              next={Boolean(spaces.data?.next)}
              onChange={(value) => {
                setSpaceOffset(value);
                setSpace("");
              }}
            />
            <Input
              label={t("storage.admin.restore_path")}
              required
              value={path}
              onChange={(event) => setPath(event.target.value)}
            />
            {(error || spaces.isError) && (
              <p role="alert">{t("storage.admin.failed")}</p>
            )}
            <Button type="submit" disabled={pending || !space || !path.trim()}>
              {t("storage.admin.restore")}
            </Button>
          </form>
        </Modal>
      )}
    </section>
  );
};
