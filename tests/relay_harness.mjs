// Test harness for bin/agent-city-relay.js, the Cloudflare Worker relay.
//
// Runs the Worker under plain Node with a stand-in for Cloudflare D1 built on
// node:sqlite (in memory), so the tests never touch Cloudflare, the network
// or a real key.
//
//   node relay_harness.mjs <worker.js> run
//       stdin:  {"env": {"TEAM_KEY": "..."} , "requests": [
//                  {"method": "POST", "path": "/v1/sync",
//                   "headers": {...}, "body": <object or raw string>,
//                   "now": <ms since epoch, optional>}, ...]}
//       stdout: {"responses": [{"status": n, "body": <parsed JSON or text>}],
//                "rows_total": <rows in every table not named sqlite_*>,
//                "full_scans": [{"sql": ..., "detail": "SCAN <table>"}, ...]}
//       full_scans: every statement whose SQLite query plan reads a whole
//       table (a plan row starting "SCAN " on a table not named sqlite_*).
//       D1's free plan counts every row a query reads, so the relay must
//       find its rows through an index, not by reading the table.
//
//   node relay_harness.mjs <worker.js> serve <TEAM_KEY>
//       A real HTTP server on 127.0.0.1, a free port, in front of the
//       Worker. Prints the port as its first line, then serves until killed.
//
// The D1 stand-in offers what a Worker may use: env.DB.prepare(sql)
// .bind(...).run() / .all() / .first(col?) / .raw(), env.DB.batch([...]) and
// env.DB.exec(sql). Nothing else. Like real D1, exec() runs each LINE of its
// input as its own statement, so a statement written over several lines
// only works through prepare().

import { DatabaseSync } from "node:sqlite";
import { copyFileSync, mkdtempSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const fullScans = [];

function notePlan(db, sql, args) {
  let rows = [];
  try {
    rows = db.prepare("EXPLAIN QUERY PLAN " + sql).all(...(args || []));
  } catch (_) {
    return;
  }
  for (const r of rows) {
    const m = /^SCAN (\S+)/.exec(r.detail || "");
    if (m && !m[1].startsWith("sqlite_")) fullScans.push({ sql: sql.trim(), detail: r.detail });
  }
}

class Stmt {
  constructor(db, sql, args) {
    this.db = db;
    this.sql = sql;
    this.args = args || [];
  }
  bind(...args) {
    return new Stmt(this.db, this.sql, args);
  }
  prep() {
    notePlan(this.db, this.sql, this.args);
    return this.db.prepare(this.sql);
  }
  async run() {
    const r = this.prep().run(...this.args);
    return { success: true, results: [],
             meta: { last_row_id: Number(r.lastInsertRowid), changes: Number(r.changes) } };
  }
  async all() {
    const rows = this.prep().all(...this.args);
    return { success: true, results: rows, meta: {} };
  }
  async first(col) {
    const row = this.prep().get(...this.args);
    if (row === undefined || row === null) return null;
    return col === undefined ? row : (row[col] === undefined ? null : row[col]);
  }
  async raw() {
    return this.prep().all(...this.args).map((r) => Object.values(r));
  }
}

class FakeD1 {
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
    // Real D1: one statement per line.
    let count = 0;
    for (const line of sql.split("\n")) {
      if (!line.trim()) continue;
      notePlan(this.db, line, []);
      this.db.exec(line);
      count += 1;
    }
    return { count, duration: 0 };
  }
  rowsTotal() {
    const tables = this.db
      .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
      .all();
    let n = 0;
    for (const t of tables) {
      n += Number(this.db.prepare(`SELECT COUNT(*) AS c FROM "${t.name}"`).get().c);
    }
    return n;
  }
}

async function loadWorker(path) {
  // The Worker is one plain ES module file; Node needs .mjs to read it as one.
  const dir = mkdtempSync(join(tmpdir(), "relay_worker_"));
  const copy = join(dir, "worker.mjs");
  copyFileSync(path, copy);
  const mod = await import(pathToFileURL(copy).href);
  if (!mod.default || typeof mod.default.fetch !== "function") {
    throw new Error("worker has no default export with fetch()");
  }
  return mod.default;
}

async function asResult(resp) {
  const text = await resp.text();
  let body = text;
  try {
    body = JSON.parse(text);
  } catch (_) {
    // keep the text
  }
  return { status: resp.status, body };
}

const realNow = Date.now;

async function runMode(worker) {
  const input = JSON.parse(readFileSync(0, "utf8"));
  const env = Object.assign({}, input.env || {});
  const d1 = new FakeD1();
  env.DB = d1;
  const responses = [];
  for (const req of input.requests) {
    Date.now = req.now === undefined ? realNow : () => req.now;
    const init = { method: req.method || "GET", headers: req.headers || {} };
    if (req.body !== undefined && init.method !== "GET" && init.method !== "HEAD") {
      init.body = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
    }
    const ctx = { waitUntil() {}, passThroughOnException() {} };
    try {
      const resp = await worker.fetch(new Request("https://relay.test" + req.path, init), env, ctx);
      responses.push(await asResult(resp));
    } catch (err) {
      responses.push({ status: -1, body: String(err && err.stack || err) });
    }
  }
  Date.now = realNow;
  process.stdout.write(JSON.stringify({ responses, rows_total: d1.rowsTotal(),
                                        full_scans: fullScans }) + "\n");
}

async function serveMode(worker, key) {
  const env = { TEAM_KEY: key, DB: new FakeD1() };
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
  server.listen(0, "127.0.0.1", () => {
    process.stdout.write(server.address().port + "\n");
  });
}

const [workerPath, mode, key] = process.argv.slice(2);
const worker = await loadWorker(workerPath);
if (mode === "serve") {
  await serveMode(worker, key);
} else {
  await runMode(worker);
}
