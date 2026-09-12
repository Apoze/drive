/** Capture display metadata before SSO. The private upload verifier stays on the device. */
export function mobileIntakeMetadata(request: string) {
  const key = `mobile-intake:${request}`;
  const url = new URL(window.location.href);
  const encoded = new URLSearchParams(url.hash.slice(1)).get("apoze-intake");
  if (encoded !== null) {
    window.history.replaceState(window.history.state, "", url.pathname + url.search);
  }
  try {
    if (!/^[a-f0-9-]{36}$/.test(request)) return;
    if (encoded !== null) {
      if (encoded.length > 4096 || !/^[A-Za-z0-9_-]+$/.test(encoded)) return;
      const bytes = Uint8Array.from(atob(encoded.replace(/-/g, "+").replace(/_/g, "/")), character => character.charCodeAt(0));
      const data = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
      if (typeof data.name !== "string" || data.name.length < 1 || data.name.length > 255 ||
          !Number.isSafeInteger(data.size) || data.size < 0 || data.size > 20 * 1024 ** 3 ||
          typeof data.mimetype !== "string" || !/^[\w.+-]+\/[\w.+-]+$/.test(data.mimetype) ||
          typeof data.challenge !== "string" || !/^[a-f0-9]{64}$/.test(data.challenge)) return;
      sessionStorage.setItem(key, JSON.stringify({ ...data, expires: Date.now() + 3600_000 }));
    }
    const data = JSON.parse(sessionStorage.getItem(key) || "null");
    if (data?.expires > Date.now()) return data as { name: string; size: number; mimetype: string; challenge: string };
    sessionStorage.removeItem(key);
  } catch { /* An invalid or unavailable local draft grants no upload permission. */ }
}
