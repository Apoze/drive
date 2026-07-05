export const createArchiveZipWorker = () =>
  new Worker(new URL("./workers/zip.worker.ts", import.meta.url), {
    type: "module",
  });
