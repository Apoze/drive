import { useEffect, useRef, useState } from "react";
import { fetchAPI } from "@/features/api/fetchApi";
import { APIError, errorToString } from "@/features/api/APIError";
import { StorageResource } from "@/features/storage/api";

type FileMetadata = { name: string; size: number; mimetype: string };
type Intake = { job_id: string; received: number; size: number; state: string; reason: string; id?: string; chunk_size: number };
const CHUNK_BYTES = 25 * 1024 ** 2;

export function useTransferIntake(enabled: boolean, origin: string, request: string) {
  const [file, setFile] = useState<FileMetadata>();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [saved, setSaved] = useState<{ id: string; space: string }>();
  const [needsLogin, setNeedsLogin] = useState(false);
  const [resume, setResume] = useState<{ id: string; space: string; title: string; filename: string }>();
  const pending = useRef<{ offset: number; length: number; resolve: (value: { bytes: ArrayBuffer; digest: string }) => void; reject: (error: Error) => void } | undefined>(undefined);
  const abort = useRef<AbortController | undefined>(undefined);
  const job = useRef<string | undefined>(undefined);
  const send = (data: Record<string, unknown>) => window.opener?.postMessage({ ...data, request }, origin);
  const api = async (path: string, options?: RequestInit): Promise<Intake> => {
    const result = await fetchAPI(path, options, { redirectOn40x: false, timeoutMs: 60_000 });
    return result.json();
  };

  useEffect(() => {
    if (!enabled || !origin || !request || !window.opener) return;
    try {
      const remembered = JSON.parse(sessionStorage.getItem(`transfer-intake:${request}`) || "null");
      if (remembered && remembered.expires > Date.now() &&
          /^[a-f0-9-]{36}$/.test(remembered.id) && /^[a-f0-9-]{36}$/.test(remembered.space) &&
          typeof remembered.title === "string" && typeof remembered.filename === "string") {
        setResume(remembered);
      }
    } catch { /* This is display state only; server authorization remains mandatory. */ }
    const receive = (event: MessageEvent) => {
      if (event.origin !== origin || event.source !== window.opener || event.data?.request !== request) return;
      const message = event.data;
      if (message.type === "transfer-intake-file" && !job.current) {
        if (typeof message.name !== "string" || !message.name || message.name.length > 255 ||
            !Number.isSafeInteger(message.size) || message.size < 0 || message.size > 20 * 1024 ** 3 ||
            typeof message.mimetype !== "string" || !/^[\w.+-]+\/[\w.+-]+$/.test(message.mimetype)) return;
        setFile({ name: message.name, size: message.size, mimetype: message.mimetype });
      } else if (message.type === "transfer-intake-block" && pending.current) {
        const expected = pending.current;
        if (message.offset !== expected.offset || !(message.bytes instanceof ArrayBuffer) ||
            message.bytes.byteLength !== expected.length || !/^[0-9a-f]{64}$/.test(message.digest)) return;
        pending.current = undefined;
        expected.resolve({ bytes: message.bytes, digest: message.digest });
      } else if (message.type === "transfer-intake-error") {
        pending.current?.reject(new Error("transfer_intake.source_error"));
        pending.current = undefined;
      }
    };
    window.addEventListener("message", receive);
    send({ type: "transfer-intake-ready" });
    return () => {
      window.removeEventListener("message", receive);
      abort.current?.abort();
      pending.current?.reject(new Error("transfer_intake.cancelled"));
      pending.current = undefined;
    };
  }, [enabled, origin, request]);

  const copy = async (destination: StorageResource, name: string) => {
    if (!file || busy || done) return;
    const controller = new AbortController();
    abort.current = controller;
    setBusy(true);
    setError("");
    setNeedsLogin(false);
    try {
      try {
        sessionStorage.setItem(`transfer-intake:${request}`, JSON.stringify({
          id: destination.id, space: destination.space, title: destination.title,
          filename: name.trim() || file.name, expires: Date.now() + 3600_000,
        }));
      } catch { /* Storage-disabled browsers can reselect the same destination manually. */ }
      let result = await api("transfer-intakes/", { method: "POST", signal: controller.signal,
        body: JSON.stringify({ request_key: request, destination: destination.id,
          space: destination.space, name: name.trim() || file.name, size: file.size, mimetype: file.mimetype }) });
      job.current = result.job_id;
      const path = `transfer-intakes/${result.job_id}/`;
      // The zero-byte block still authenticates the encrypted empty source.
      let emptyVerified = file.size !== 0;
      while (result.received < file.size || !emptyVerified) {
        if (result.state === "done") break;
        if (result.state === "failed" || result.state === "conflict") throw new Error("transfer_intake.failed");
        const offset = result.received;
        const length = Math.min(CHUNK_BYTES, file.size - offset);
        const block = await new Promise<{ bytes: ArrayBuffer; digest: string }>((resolve, reject) => {
          const timer = setTimeout(() => { pending.current = undefined; reject(new Error("transfer_intake.source_error")); }, 90_000);
          const cancel = () => { clearTimeout(timer); pending.current = undefined; reject(new Error("transfer_intake.cancelled")); };
          controller.signal.addEventListener("abort", cancel, { once: true });
          const cleanup = () => { clearTimeout(timer); controller.signal.removeEventListener("abort", cancel); };
          pending.current = { offset, length, resolve: value => { cleanup(); resolve(value); },
            reject: reason => { cleanup(); reject(reason); } };
          send({ type: "transfer-intake-pull", offset, length });
        });
        result = await api(path, { method: "PUT", signal: controller.signal,
          body: block.bytes, headers: { "Content-Type": "application/octet-stream",
            "X-Upload-Offset": String(offset), "X-Content-SHA256": block.digest } });
        emptyVerified = true;
        setProgress(file.size ? Math.floor(90 * result.received / file.size) : 90);
      }
      result = await api(path, { method: "PATCH", body: "{}", signal: controller.signal });
      while (result.state !== "done") {
        if (result.state === "failed" || result.state === "conflict") throw new Error("transfer_intake.failed");
        await new Promise(resolve => setTimeout(resolve, 2000));
        if (controller.signal.aborted) throw new Error("transfer_intake.cancelled");
        result = await api(path, { signal: controller.signal });
        // Reauthenticate explicitly if needed; never convert a short proof into an unlimited lease.
      }
      setProgress(100);
      if (!result.id) throw new Error("transfer_intake.retry");
      setSaved({ id: result.id, space: destination.space });
      setDone(true);
    } catch (failure) {
      setNeedsLogin(failure instanceof APIError && failure.code === 401);
      if (!controller.signal.aborted) setError(failure instanceof Error && failure.message.startsWith("transfer_intake.")
        ? failure.message : failure instanceof APIError ? errorToString(failure) : "transfer_intake.retry");
    } finally { setBusy(false); }
  };

  const cancel = async () => {
    abort.current?.abort();
    try {
      if (job.current && !done) await fetchAPI(`transfer-intakes/${job.current}/`, { method: "DELETE" }, { redirectOn40x: false, timeoutMs: 60_000 });
      try { sessionStorage.removeItem(`transfer-intake:${request}`); } catch { /* Optional display state. */ }
      send({ type: done ? "transfer-intake-done" : "transfer-intake-cancel" });
      window.close();
    } catch { setError("transfer_intake.cancel_pending"); }
  };
  return { file, busy, progress, error, done, saved, resume, needsLogin, copy, cancel };
}
