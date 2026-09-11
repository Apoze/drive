import { fetchAPI } from "@/features/api/fetchApi";
import { StorageResource } from "@/features/storage/api";

// Matches the native Chat upload ceiling; encryption uses the native client.
export const CHAT_COPY_MAX_BYTES = 100 * 1024 ** 2;

export async function chatCopy(resource: StorageResource, principal: string): Promise<File> {
  const headers = { "X-Suite-Principal": principal };
  const request = (path: string, method: string, data: object) => fetchAPI(path, {
    method, headers, body: JSON.stringify(data),
  }, { redirectOn40x: false, timeoutMs: 120_000 });
  const selection = { resource: resource.id, space: resource.space, export: resource.kind === "docs" };
  if (resource.kind === "docs") {
    const result = await request("chat-files/", "POST", selection);
    const length = Number(result.headers.get("Content-Length"));
    if (!Number.isSafeInteger(length) || length < 0 || length > 25 * 1024 ** 2) throw new Error("Invalid export size");
    const bytes = await result.arrayBuffer();
    if (bytes.byteLength !== length) throw new Error("Incomplete export");
    return new File([bytes], resource.title + ".pdf", { type: "application/pdf" });
  }
  const metadata = await (await request("chat-files/chunks/", "PATCH", selection)).json();
  if (!Number.isSafeInteger(metadata.size) || metadata.size < 0 || metadata.size > CHAT_COPY_MAX_BYTES) throw new Error("Copy exceeds Chat limit");
  const parts: ArrayBuffer[] = [];
  let offset = 0;
  do {
    const length = Math.min(25 * 1024 ** 2, metadata.size - offset);
    const result = await request("chat-files/chunks/", "POST", { snapshot: metadata.snapshot, offset, length });
    const bytes = await result.arrayBuffer();
    if (bytes.byteLength !== length) throw new Error("Incomplete source");
    // Drive rechecks the observed source version before/after every bounded read.
    parts.push(bytes);
    offset += length;
  } while (offset < metadata.size);
  return new File(parts, metadata.name, { type: metadata.mimetype });
}
