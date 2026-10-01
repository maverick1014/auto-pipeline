#!/usr/bin/env node
// agent-city-cloud-dev.mjs — the dev runner for the cloud city (cloud-city-1).
// Runs the two Workers, bin/agent-city-relay.js and bin/agent-city-cloud.js,
// the very files that go to Cloudflare, behind ONE plain node:http server on
// one local port, with one shared in-memory stand-in for D1 (node:sqlite) and
// a stand-in for the static assets. No Cloudflare account, nothing leaves
// this machine.
//
//   node agent-city-cloud-dev.mjs --user <e-mail> [--talk] [--host H] [--port P] [--no-login]
//     The team key is the first line of stdin: never argv, never printed.
//     --talk (talk from the cloud page): the SECOND line of stdin is the talk
//     key, the relay's TALK_KEY (never argv, never printed). Without --talk
//     the relay has no TALK_KEY (talking is off), as before. --talk and no
//     second line (or an empty one) -> exit 2.
//     Default host 127.0.0.1 (the login is simulated: never the LAN by
//     default), default port 8788; --port 0 = any free port.
//     stdout, first two lines:
//       CLOUD-DEV: listening on <host>:<port>
//       CLOUD-DEV: page http://<host>:<port>/  relay http://<host>:<port>
//     /v1/...    -> the relay  (TEAM_KEY = the key, CITY_USER = --user,
//                   TALK_KEY = the second line, only with --talk)
//     the rest   -> the City Worker, as if Cloudflare Access had let --user
//                   in: the runner signs a token for it with its own key pair
//                   (made at start) and answers the Worker's certs fetch
//                   itself. --no-login: no token is added (everything is 403).
//                   A POST (the page's /api/chat/send) arrives whole: its
//                   method, headers (Origin too) and body. The request URL the
//                   Worker sees is http://<the Host header of the browser>, so
//                   its origin is the one the browser used and the Worker's
//                   Origin check (Origin == its own origin) holds.
//     ASSETS: / (and /index.html) = bin/agent-city.html, /assets/<p> =
//     bin/agent-city-assets/<p> (never a path outside that folder).
//     No --user -> exit 2. Empty key -> exit 2. Stops on SIGINT / SIGTERM.
//
// Needs Node 22.5+ (node:sqlite).

import { DatabaseSync } from "node:sqlite";
import { copyFileSync, mkdtempSync, rmSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { dirname, extname, join as joinPath, resolve as resolvePath, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createSign, generateKeyPairSync } from "node:crypto";

const HERE = dirname(fileURLToPath(import.meta.url));
const RELAY_PATH = joinPath(HERE, "agent-city-relay.js");
const CITY_PATH = joinPath(HERE, "agent-city-cloud.js");
const PAGE_PATH = joinPath(HERE, "agent-city.html");
const ASSETS_DIR = joinPath(HERE, "agent-city-assets");

// What the City Worker is told, and what the signed token says.
const DEV_TEAM = "devteam";
const DEV_ISSUER = `https://${DEV_TEAM}.cloudflareaccess.com`;
const DEV_CERTS_URL = `${DEV_ISSUER}/cdn-cgi/access/certs`;
const DEV_AUD = "agent-city-cloud-dev-audience";
const DEV_KID = "dev1";

// Say why on stderr, then exit 2 (stdin may still be open: do not wait for it).
function fail(message) {
  process.exitCode = 2;
  process.stderr.write(`CLOUD-DEV: ${message}\n`, () => process.exit(2));
}

function parseArgs(argv) {
  const out = { host: "127.0.0.1", port: 8788, user: "", noLogin: false, talk: false, bad: "" };
  for (let i = 0; i < argv.length; i++) {
    let name = argv[i];
    let value;
    const eq = name.indexOf("=");
    if (name.startsWith("--") && eq > 0) {
      value = name.slice(eq + 1);
      name = name.slice(0, eq);
    }
    const next = () => (value !== undefined ? value : argv[++i]);
    if (name === "--user") {
      out.user = String(next() || "").trim();
    } else if (name === "--host") {
      out.host = String(next() || "");
    } else if (name === "--port") {
      const text = String(next() || "");
      const port = /^[0-9]{1,5}$/.test(text) ? Number(text) : -1;
      if (port < 0 || port > 65535) out.bad = "--port needs a number from 0 to 65535";
      else out.port = port;
    } else if (name === "--no-login") {
      out.noLogin = true;
    } else if (name === "--talk") {
      out.talk = true;
    }
  }
  return out;
}

// A stand-in for Cloudflare D1, in memory, on node:sqlite. Offers what the
// Workers may use: prepare(sql).bind(...).run()/.all()/.first(col?)/.raw(),
// batch([...]) and exec(sql). Like real D1, exec() runs each LINE of its
// input as its own statement.
class Stmt {
  constructor(db, sql, args) {
    this.db = db;
    this.sql = sql;
    this.args = args || [];
  }
  bind(...args) {
    return new Stmt(this.db, this.sql, args);
  }
  async run() {
    const r = this.db.prepare(this.sql).run(...this.args);
    return { success: true, results: [],
             meta: { last_row_id: Number(r.lastInsertRowid), changes: Number(r.changes) } };
  }
  async all() {
    const rows = this.db.prepare(this.sql).all(...this.args);
    return { success: true, results: rows, meta: {} };
  }
  async first(col) {
    const row = this.db.prepare(this.sql).get(...this.args);
    if (row === undefined || row === null) return null;
    return col === undefined ? row : (row[col] === undefined ? null : row[col]);
  }
  async raw() {
    return this.db.prepare(this.sql).all(...this.args).map((r) => Object.values(r));
  }
}

class DevD1 {
  constructor() {
    this.db = new DatabaseSync(":memory:");
  }
  prepare(sql) {
    return new Stmt(this.db, sql, []);
  }
  async batch(stmts) {
    this.db.exec("BEGIN");
    try {
      const out = [];
      for (const s of stmts) out.push(await s.all());
      this.db.exec("COMMIT");
      return out;
    } catch (err) {
      this.db.exec("ROLLBACK");
      throw err;
    }
  }
  async exec(sql) {
    let count = 0;
    for (const line of sql.split("\n")) {
      if (!line.trim()) continue;
      this.db.exec(line);
      count += 1;
    }
    return { count, duration: 0 };
  }
}

async function loadWorker(path, tag) {
  // A Worker is one plain ES module file; Node needs .mjs to read it as one.
  const dir = mkdtempSync(joinPath(tmpdir(), "cloud_dev_"));
  try {
    const copy = joinPath(dir, tag + ".mjs");
    copyFileSync(path, copy);
    const mod = await import(pathToFileURL(copy).href);
    if (!mod.default || typeof mod.default.fetch !== "function") {
      throw new Error(tag + " worker has no default export with fetch()");
    }
    return mod.default;
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// The first `count` lines of stdin, without their newlines. Resolves with the
// lines it got (fewer than `count` when stdin ends first; the last one may
// then be a line without its newline, "" when there was nothing).
function readLines(count) {
  return new Promise((resolve) => {
    let buf = "";
    const lines = [];
    const cleanup = () => {
      process.stdin.off("data", onData);
      process.stdin.off("end", onEnd);
      process.stdin.pause();
    };
    const onData = (chunk) => {
      buf += chunk;
      let idx;
      while (lines.length < count && (idx = buf.indexOf("\n")) !== -1) {
        lines.push(buf.slice(0, idx).replace(/\r$/, ""));
        buf = buf.slice(idx + 1);
      }
      if (lines.length >= count) {
        cleanup();
        resolve(lines);
      }
    };
    const onEnd = () => {
      cleanup();
      if (lines.length < count) lines.push(buf.replace(/\r$/, ""));
      resolve(lines);
    };
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", onData);
    process.stdin.on("end", onEnd);
    process.stdin.resume();
  });
}

// ---- Cloudflare Access stand-in: a key pair, tokens, and the certs answer ----

const b64u = (buf) => Buffer.from(buf).toString("base64url");

function makeAccess(user) {
  const pair = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const jwk = Object.assign(pair.publicKey.export({ format: "jwk" }),
                            { kid: DEV_KID, alg: "RS256", use: "sig" });
  return {
    jwk,
    token() {
      const now = Math.floor(Date.now() / 1000);
      const head = b64u(JSON.stringify({ alg: "RS256", kid: DEV_KID, typ: "JWT" })) + "." +
        b64u(JSON.stringify({ aud: [DEV_AUD], email: user, iss: DEV_ISSUER, iat: now - 5, nbf: now - 5,
                              exp: now + 3600, sub: "dev-user", type: "app" }));
      const signer = createSign("RSA-SHA256");
      signer.update(head);
      return head + "." + b64u(signer.sign(pair.privateKey));
    },
  };
}

// The Worker's own fetch() is all it has for the network: answer the team's
// certs here, and nothing else (nothing leaves this machine).
function wrapFetch(access) {
  globalThis.fetch = async (input) => {
    const url = typeof input === "string" ? input : (input && input.url) || String(input);
    if (url === DEV_CERTS_URL) {
      return new Response(JSON.stringify({ keys: [access.jwk], public_cert: {}, public_certs: [] }),
                          { status: 200, headers: { "content-type": "application/json" } });
    }
    throw new Error("CLOUD-DEV has no network: " + url);
  };
}

// ---- static assets stand-in ----

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript",
  ".css": "text/css", ".json": "application/json", ".txt": "text/plain", ".svg": "image/svg+xml",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
  ".webp": "image/webp", ".glb": "model/gltf-binary", ".gltf": "model/gltf+json",
  ".bin": "application/octet-stream", ".mtl": "text/plain", ".obj": "text/plain",
  ".woff": "font/woff", ".woff2": "font/woff2", ".wasm": "application/wasm",
};

function notFound() {
  return new Response("not found", { status: 404 });
}

async function sendFile(path) {
  const body = await readFile(path);
  return new Response(body, {
    status: 200,
    headers: { "content-type": TYPES[extname(path).toLowerCase()] || "application/octet-stream" },
  });
}

const assetsBinding = {
  async fetch(request) {
    const url = new URL(typeof request === "string" ? request : request.url);
    let path;
    try {
      path = decodeURIComponent(url.pathname);
    } catch (err) {
      return notFound();
    }
    if (path.includes("\0") || path.includes("\\")) return notFound();
    if (path === "/" || path === "/index.html") return sendFile(PAGE_PATH);
    if (!path.startsWith("/assets/")) return notFound();
    const full = resolvePath(ASSETS_DIR, path.slice("/assets/".length));
    if (!full.startsWith(ASSETS_DIR + sep)) return notFound();
    try {
      if (!statSync(full).isFile()) return notFound();
    } catch (err) {
      return notFound();
    }
    return sendFile(full);
  },
};

// ---- the server ----

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.bad) return fail(args.bad);
  if (!args.user) return fail("need --user <e-mail>");
  const lines = await readLines(args.talk ? 2 : 1);
  const key = lines[0] || "";
  if (!key) return fail("no key on stdin");
  const talkKey = args.talk ? (lines[1] || "") : "";
  if (args.talk && !talkKey) return fail("--talk needs the talk key as the second line of stdin");

  const access = makeAccess(args.user);
  wrapFetch(access);
  const relay = await loadWorker(RELAY_PATH, "relay");
  const city = await loadWorker(CITY_PATH, "city");

  const db = new DevD1();
  const relayEnv = { TEAM_KEY: key, CITY_USER: args.user, DB: db };
  if (args.talk) relayEnv.TALK_KEY = talkKey;
  const cityEnv = { DB: db, ASSETS: assetsBinding, ACCESS_TEAM: DEV_TEAM, ACCESS_AUD: DEV_AUD };
  const ctx = { waitUntil() {}, passThroughOnException() {} };

  const server = createServer(async (req, res) => {
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const headers = new Headers();
    for (const [name, value] of Object.entries(req.headers)) {
      headers.set(name, Array.isArray(value) ? value.join(", ") : String(value));
    }
    const toRelay = req.url === "/v1" || req.url.startsWith("/v1/") || req.url.startsWith("/v1?");
    if (!toRelay) {
      // What Cloudflare Access does: its own token, whatever the client sent.
      headers.delete("cf-access-jwt-assertion");
      if (!args.noLogin) headers.set("cf-access-jwt-assertion", access.token());
    }
    const init = { method: req.method, headers };
    if (chunks.length && req.method !== "GET" && req.method !== "HEAD") {
      init.body = Buffer.concat(chunks);
    }
    let resp;
    try {
      const request = new Request("http://" + (req.headers.host || `${args.host}:${server.address().port}`) + req.url, init);
      resp = toRelay ? await relay.fetch(request, relayEnv, ctx) : await city.fetch(request, cityEnv, ctx);
    } catch (err) {
      process.stderr.write(`CLOUD-DEV: worker error: ${err && err.message ? err.message : err}\n`);
      res.writeHead(500, { "content-type": "text/plain" });
      res.end("CLOUD-DEV: worker error");
      return;
    }
    const out = {};
    resp.headers.forEach((v, k) => { out[k] = v; });
    res.writeHead(resp.status, out);
    res.end(Buffer.from(await resp.arrayBuffer()));
  });

  server.listen(args.port, args.host, () => {
    const port = server.address().port;
    process.stdout.write(`CLOUD-DEV: listening on ${args.host}:${port}\n`);
    process.stdout.write(`CLOUD-DEV: page http://${args.host}:${port}/  relay http://${args.host}:${port}\n`);
  });

  const shutdown = () => {
    server.close(() => process.exit(0));
    if (server.closeAllConnections) server.closeAllConnections();
    setTimeout(() => process.exit(0), 2000).unref();
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((err) => {
  process.stderr.write(`CLOUD-DEV: ${err && err.message ? err.message : err}\n`);
  process.exitCode = 1;
});
