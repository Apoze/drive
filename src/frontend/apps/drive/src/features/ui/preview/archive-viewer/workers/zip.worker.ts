/// <reference lib="webworker" />

import {
  BlobReader,
  HttpRangeReader,
  type HttpRangeOptions,
  TextWriter,
  Uint8ArrayWriter,
  type Entry,
  ZipReader,
} from "@zip.js/zip.js";

type ArchiveEntry = {
  path: string;
  isDirectory: boolean;
  uncompressedSize: number;
  compressedSize?: number;
  lastModified?: number | null;
};

type ZipWorkerRequest =
  | { requestId: number; type: "list"; url: string }
  | { requestId: number; type: "readText"; url: string; path: string }
  | { requestId: number; type: "readBinary"; url: string; path: string };

type ZipWorkerResponse =
  | { requestId: number; type: "list:ok"; entries: ArchiveEntry[] }
  | { requestId: number; type: "readText:ok"; text: string }
  | { requestId: number; type: "readBinary:ok"; buffer: ArrayBuffer }
  | { requestId: number; type: "error"; message: string; code?: string };

let currentUrl: string | null = null;
let reader: ZipReader<Entry> | null = null;
let cachedEntries: Entry[] | null = null;

const ctx: DedicatedWorkerGlobalScope = self as unknown as DedicatedWorkerGlobalScope;

const closeReader = async () => {
  try {
    await reader?.close();
  } catch {
    // ignore
  } finally {
    reader = null;
    cachedEntries = null;
    currentUrl = null;
  }
};

const openReader = async (url: string) => {
  if (currentUrl === url && reader && cachedEntries) {
    return;
  }
  await closeReader();
  currentUrl = url;

  try {
    const httpOptions: HttpRangeOptions & {
      credentials: RequestCredentials;
      preventHeadRequest: boolean;
    } = {
      // TypeScript types don't expose it, but it is forwarded to fetch().
      credentials: "include",
      // Avoid an explicit HEAD in some CORS setups; rely on Content-Range instead.
      preventHeadRequest: true,
    };
    const httpReader = new HttpRangeReader(url, httpOptions);
    reader = new ZipReader(httpReader);
    cachedEntries = await reader.getEntries();
    return;
  } catch {
    // Fallback: download the full archive (no Range support / proxy limitations).
    const resp = await fetch(url, { credentials: "include" });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    const blob = await resp.blob();
    reader = new ZipReader(new BlobReader(blob));
    cachedEntries = await reader.getEntries();
  }
};

const summarizeEntries = (entries: Entry[]): ArchiveEntry[] => {
  return entries.map((e) => ({
    path: e.filename,
    isDirectory: Boolean(e.directory),
    uncompressedSize: Number(e.uncompressedSize ?? 0),
    compressedSize: Number(e.compressedSize ?? 0),
    lastModified: e.lastModDate ? new Date(e.lastModDate).getTime() : null,
  }));
};

const findEntry = (path: string) => {
  if (!cachedEntries) return null;
  return cachedEntries.find((e) => e.filename === path) ?? null;
};

self.onmessage = async (event: MessageEvent<ZipWorkerRequest>) => {
  const payload = event.data;
  const requestId = payload.requestId;
  try {
    if (payload.type === "list") {
      await openReader(payload.url);
      const entries = summarizeEntries(cachedEntries ?? []);
      self.postMessage({
        requestId,
        type: "list:ok",
        entries,
      } satisfies ZipWorkerResponse);
      return;
    }

    if (payload.type === "readText") {
      await openReader(payload.url);
      const entry = findEntry(payload.path);
      if (!entry || entry.directory) {
        self.postMessage({
          requestId,
          type: "error",
          message: "File not found in archive.",
        } satisfies ZipWorkerResponse);
        return;
      }
      const text = await entry.getData(new TextWriter());
      self.postMessage({
        requestId,
        type: "readText:ok",
        text,
      } satisfies ZipWorkerResponse);
      return;
    }

    if (payload.type === "readBinary") {
      await openReader(payload.url);
      const entry = findEntry(payload.path);
      if (!entry || entry.directory) {
        self.postMessage({
          requestId,
          type: "error",
          message: "File not found in archive.",
        } satisfies ZipWorkerResponse);
        return;
      }
      const array = await entry.getData(new Uint8ArrayWriter());
      const buffer = (array as Uint8Array).buffer.slice(0);
      ctx.postMessage(
        {
          requestId,
          type: "readBinary:ok",
          buffer,
        } satisfies ZipWorkerResponse,
        [buffer]
      );
      return;
    }

    self.postMessage({
      requestId,
      type: "error",
      message: "Unsupported worker message.",
    } satisfies ZipWorkerResponse);
  } catch (e) {
    self.postMessage({
      requestId,
      type: "error",
      message: e instanceof Error ? e.message : "Unknown error.",
    } satisfies ZipWorkerResponse);
  }
};
