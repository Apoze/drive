/* eslint-disable no-console */
const http = require("http");
const net = require("net");
const { URL } = require("url");

const bindHost = process.env.E2E_LOOPBACK_BIND_HOST || "127.0.0.1";

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
  { name: "ui", port: 3000, upstream: uiUpstream },
  { name: "api", port: 8071, upstream: apiUpstream },
  { name: "edge", port: 8083, upstream: edgeUpstream },
  // S3 gateway is exposed on host as :9000 in the dev stack and is used for
  // presigned PUTs (AWS_S3_DOMAIN_REPLACE=http://localhost:9000). Keep it
  // reachable inside the Playwright container by proxying localhost:9000.
  { name: "s3", port: 9000, upstream: s3Upstream },
];

const createProxyServer = ({ name, port, upstream }) => {
  const server = http.createServer((req, res) => {
    try {
      if (!req.url) {
        res.statusCode = 400;
        res.end("Missing url");
        return;
      }

      const target = new URL(req.url, upstream);

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
          res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
          proxyRes.pipe(res);
        }
      );

      proxyReq.on("error", () => {
        res.statusCode = 502;
        res.end("Bad gateway");
      });

      req.pipe(proxyReq);
    } catch {
      res.statusCode = 502;
      res.end("Bad gateway");
    }
  });

  server.on("clientError", (_err, socket) => {
    socket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
  });

  server.on("upgrade", (req, socket, head) => {
    try {
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
