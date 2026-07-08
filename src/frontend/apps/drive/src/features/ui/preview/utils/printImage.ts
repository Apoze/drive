export const printImage = (imageUrl: string) => {
  const iframe = document.createElement("iframe");

  iframe.setAttribute("aria-hidden", "true");
  iframe.style.position = "fixed";
  iframe.style.right = "0";
  iframe.style.bottom = "0";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "0";

  const cleanup = () => {
    iframe.remove();
  };

  iframe.addEventListener(
    "load",
    () => {
      const frameWindow = iframe.contentWindow;
      const frameDocument = iframe.contentDocument;

      if (!frameWindow || !frameDocument) {
        cleanup();
        return;
      }

      const style = frameDocument.createElement("style");
      style.textContent =
        "@page { margin: 0; } html, body { margin: 0; padding: 0; height: 100%; } img { display: block; max-width: 100%; max-height: 100vh; margin: auto; }";
      frameDocument.head.appendChild(style);

      const image = frameDocument.createElement("img");
      image.alt = "";
      image.addEventListener(
        "load",
        () => {
          frameWindow.focus();
          frameWindow.print();
        },
        { once: true },
      );
      image.addEventListener("error", cleanup, { once: true });
      frameWindow.addEventListener("afterprint", cleanup, { once: true });
      image.src = imageUrl;
      frameDocument.body.appendChild(image);
    },
    { once: true },
  );

  iframe.src = "about:blank";
  document.body.appendChild(iframe);
};
