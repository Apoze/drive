/* eslint-disable no-console */
const http = require("http");
const net = require("net");
const { URL } = require("url");

const bindHost = process.env.E2E_LOOPBACK_BIND_HOST || "127.0.0.1";
const baseUrl = new URL(process.env.E2E_BASE_URL || "http://127.0.0.1:3000");
const apiOrigin = new URL(
  process.env.E2E_API_ORIGIN || "http://127.0.0.1:8071"
);
const edgeOrigin = new URL(
  process.env.E2E_EDGE_ORIGIN || "http://127.0.0.1:8083"
);
const s3Origin = new URL(
  process.env.E2E_S3_ORIGIN || "http://127.0.0.1:9000"
);

const uiUpstream = new URL(
  process.env.E2E_UI_UPSTREAM || "http://frontend-dev:3000"
);
const apiUpstream = new URL(
  process.env.E2E_API_UPSTREAM || "http://app-dev:8000"
);
const edgeUpstream = new URL(
  process.env.E2E_EDGE_UPSTREAM || "http://nginx:8083"
);
const s3Upstream = new URL(
  process.env.E2E_S3_UPSTREAM || "http://seaweedfs-s3:8333"
);

const proxies = [
  { name: "ui", port: Number(baseUrl.port) || 80, upstream: uiUpstream },
  { name: "api", port: Number(apiOrigin.port) || 80, upstream: apiUpstream },
  { name: "edge", port: Number(edgeOrigin.port) || 80, upstream: edgeUpstream },
  // S3 gateway is exposed on host as :9000 in the dev stack and is used for
  // presigned PUTs (AWS_S3_DOMAIN_REPLACE=http://localhost:9000). Keep it
  // reachable inside the Playwright container by proxying localhost:9000.
  { name: "s3", port: Number(s3Origin.port) || 80, upstream: s3Upstream },
];

const getResponseHeaders = ({ name, headers }) => {
  if (name !== "ui") {
    return headers;
  }

  return {
    ...headers,
    // PR E2E runs through frontend-dev, but the browser-facing production
    // frontend nginx always serves Drive pages with this noindex header.
    "x-robots-tag": "noindex",
  };
};

const createProxyServer = ({ name, port, upstream }) => {
  const server = http.createServer((req, res) => {
    try {
      if (!req.url) {
        res.statusCode = 400;
        res.end("Missing url");
        return;
      }

      const target = new URL(req.url, upstream);

      req.on("error", () => {
        try {
          res.destroy();
        } catch {
          // ignore
        }
      });

      res.on("error", () => {
        // ignore
      });

      const proxyReq = http.request(
        {
          protocol: upstream.protocol,
          hostname: upstream.hostname,
          port: upstream.port,
          method: req.method,
          path: target.pathname + target.search,
          headers: {
            ...req.headers,
            host: req.headers.host || upstream.host,
          },
        },
        (proxyRes) => {
          proxyRes.on("error", () => {
            try {
              if (!res.headersSent) res.writeHead(502);
              res.end("Bad gateway");
            } catch {
              // ignore
            }
          });

          res.writeHead(
            proxyRes.statusCode || 502,
            getResponseHeaders({ name, headers: proxyRes.headers })
          );
          proxyRes.pipe(res);
        }
      );

      proxyReq.on("error", () => {
        try {
          res.statusCode = 502;
          res.end("Bad gateway");
        } catch {
          // ignore
        }
      });

      req.pipe(proxyReq);
    } catch {
      res.statusCode = 502;
      res.end("Bad gateway");
    }
  });

  server.on("error", (err) => {
    console.error(`[e2e] loopback proxy ${name} server error`, err);
  });

  server.on("clientError", (_err, socket) => {
    socket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
  });

  server.on("upgrade", (req, socket, head) => {
    try {
      socket.on("error", () => {
        try {
          socket.destroy();
        } catch {
          // ignore
        }
      });

      const upstreamSocket = net.connect(
        Number(upstream.port) || (upstream.protocol === "https:" ? 443 : 80),
        upstream.hostname,
        () => {
          let headerLines = "";
          for (const [key, value] of Object.entries(req.headers)) {
            if (value === undefined) continue;
            if (Array.isArray(value)) {
              for (const v of value) headerLines += `${key}: ${v}\r\n`;
              continue;
            }
            headerLines += `${key}: ${value}\r\n`;
          }

          upstreamSocket.write(
            `${req.method} ${req.url} HTTP/${req.httpVersion}\r\n${headerLines}\r\n`
          );
          if (head && head.length) upstreamSocket.write(head);
          upstreamSocket.pipe(socket);
          socket.pipe(upstreamSocket);
        }
      );

      upstreamSocket.on("error", () => {
        socket.destroy();
      });
    } catch {
      socket.destroy();
    }
  });

  server.listen(port, bindHost, () => {
    console.log(
      `[e2e] loopback proxy ${name} listening on http://${bindHost}:${port} -> ${upstream.toString()}`
    );
  });

  return server;
};

const servers = proxies.map(createProxyServer);

process.on("uncaughtException", (err) => {
  console.error("[e2e] loopback proxies uncaughtException", err);
});

process.on("unhandledRejection", (err) => {
  console.error("[e2e] loopback proxies unhandledRejection", err);
});

const shutdown = async () => {
  await Promise.all(
    servers.map(
      (s) =>
        new Promise((resolve) => {
          s.close(() => resolve());
        })
    )
  );
};

process.on("SIGINT", () => shutdown().then(() => process.exit(0)));
process.on("SIGTERM", () => shutdown().then(() => process.exit(0)));
