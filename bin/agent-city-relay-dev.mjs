#!/usr/bin/env node
// agent-city-relay-dev.mjs — the dev relay for the two-machine LAN test
// (city-join-page, step 2). Runs bin/agent-city-relay.js, the very file the
// owner pastes into Cloudflare, behind a plain node:http server, with an
// in-memory stand-in for D1 (node:sqlite) bound as DB and the team key as
// TEAM_KEY. No Cloudflare account, no network beyond this LAN.
//
//   node agent-city-relay-dev.mjs [--host H] [--port P]
//     Default host 0.0.0.0 (the LAN), default port 8787.
//     The team key is the first line of stdin: never argv, never printed.
//     stdout, first two lines:
//       RELAY-DEV: listening on <host>:<port>
//       RELAY-DEV: join with http://<this machine's LAN IPv4, or 127.0.0.1>:<port>
//     Empty key -> exit 2, "RELAY-DEV: no key on stdin".
//     Stops on SIGINT / SIGTERM.
//
// Needs Node 22.5+ (node:sqlite). See bin/agent-city.sh's `relay-dev` verb,
// which checks that and asks for the key with echo off.

import { DatabaseSync } from "node:sqlite";
import { copyFileSync, mkdtempSync } from "node:fs";
import { createServer } from "node:http";
import { networkInterfaces, tmpdir } from "node:os";
import { dirname, join as joinPath } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const WORKER_PATH = joinPath(HERE, "agent-city-relay.js");

function parseArgs(argv) {
  let host = "0.0.0.0";
  let port = 8787;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--host") {
      host = argv[++i];
    } else if (argv[i] === "--port") {
      port = Number(argv[++i]);
    }
  }
  return { host, port };
}

// A stand-in for Cloudflare D1, in memory, on node:sqlite. Offers what the
// Worker may use: prepare(sql).bind(...).run()/.all()/.first(col?)/.raw(),
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

async function loadWorker(path) {
  // The Worker is one plain ES module file; Node needs .mjs to read it as one.
  const dir = mkdtempSync(joinPath(tmpdir(), "relay_dev_"));
  const copy = joinPath(dir, "worker.mjs");
  copyFileSync(path, copy);
  const mod = await import(pathToFileURL(copy).href);
  if (!mod.default || typeof mod.default.fetch !== "function") {
    throw new Error("worker has no default export with fetch()");
  }
  return mod.default;
}

// First non-internal IPv4 in a private LAN range, else 127.0.0.1.
function lanAddress() {
  const ranges = [/^10\./, /^172\.(1[6-9]|2\d|3[01])\./, /^192\.168\./];
  const nets = networkInterfaces();
  for (const name of Object.keys(nets)) {
    for (const net of nets[name] || []) {
      const isV4 = net.family === "IPv4" || net.family === 4;
      if (isV4 && !net.internal && ranges.some((r) => r.test(net.address))) {
        return net.address;
      }
    }
  }
  return "127.0.0.1";
}

// The first line of stdin, without its trailing newline. Resolves "" when
// stdin ends before any newline (an empty key, or none at all).
function readKeyLine() {
  return new Promise((resolve) => {
    let buf = "";
    const cleanup = () => {
      process.stdin.off("data", onData);
      process.stdin.off("end", onEnd);
      process.stdin.pause();
    };
    const onData = (chunk) => {
      buf += chunk;
      const idx = buf.indexOf("\n");
      if (idx !== -1) {
        const line = buf.slice(0, idx).replace(/\r$/, "");
        cleanup();
        resolve(line);
      }
    };
    const onEnd = () => {
      cleanup();
      resolve(buf.replace(/\r$/, ""));
    };
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", onData);
    process.stdin.on("end", onEnd);
    process.stdin.resume();
  });
}

async function main() {
  const { host, port } = parseArgs(process.argv.slice(2));
  const key = await readKeyLine();
  if (!key) {
    process.stderr.write("RELAY-DEV: no key on stdin\n");
    process.exitCode = 2;
    return;
  }

  const worker = await loadWorker(WORKER_PATH);
  const env = { TEAM_KEY: key, DB: new DevD1() };

  const server = createServer(async (req, res) => {
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const init = { method: req.method, headers: req.headers };
    if (chunks.length && req.method !== "GET" && req.method !== "HEAD") {
      init.body = Buffer.concat(chunks);
    }
    let resp;
    try {
      resp = await worker.fetch(new Request("http://" + req.headers.host + req.url, init), env,
                                { waitUntil() {}, passThroughOnException() {} });
    } catch (err) {
      res.writeHead(599);
      res.end(String(err));
      return;
    }
    const headers = {};
    resp.headers.forEach((v, k) => { headers[k] = v; });
    res.writeHead(resp.status, headers);
    res.end(Buffer.from(await resp.arrayBuffer()));
  });

  server.listen(port, host, () => {
    const actualPort = server.address().port;
    process.stdout.write(`RELAY-DEV: listening on ${host}:${actualPort}\n`);
    process.stdout.write(`RELAY-DEV: join with http://${lanAddress()}:${actualPort}\n`);
  });

  const shutdown = () => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 2000).unref();
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main();
