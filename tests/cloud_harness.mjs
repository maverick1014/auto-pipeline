// Test harness for the cloud city (cloud-city-1): runs the two Workers under
// plain Node, on ONE in-memory stand-in for Cloudflare D1 (node:sqlite), with
// a stand-in for the static assets binding and for Cloudflare Access. No test
// talks to Cloudflare, the network or a real key.
//
//   node cloud_harness.mjs <relay worker.js> <city worker.js> run
//     stdin:  {"env": {"relay": {...}, "city": {...}},
//              "assets": {"/index.html": "<text>", "/assets/x.js": "<text>"},
//              "requests": [
//                {"to": "relay" | "city", "method": "GET", "path": "/api/feed",
//                 "headers": {...}, "body": <object or raw string>,
//                 "now": <ms since epoch, optional>,
//                 "login": null | {"email": "a@b.c", ...}}, ...]}
//     stdout: {"responses": [{"status", "body", "headers": {...},
//                             "writes": n, "reads": n, "stmts": n}, ...],
//              "rows_total", "full_scans", "certs_fetches", "other_fetches",
//              "assets_fetched", "dump": {"<table>": [row, ...]}}
//
//   Either worker path may be "-" when a test does not need that Worker.
//
// Cloudflare Access stand-in (the City Worker must check the token itself):
//   team   testteam  -> issuer https://testteam.cloudflareaccess.com
//   certs  https://testteam.cloudflareaccess.com/cdn-cgi/access/certs
//          answered by a stubbed global fetch with {"keys": [<JWK kid "k1">]}.
//          Every other fetch() fails and is listed in other_fetches.
//   "login" on a city request adds the header Cf-Access-Jwt-Assertion with an
//   RS256 token signed by k1: {aud: [AUD], email, iss, iat, nbf, exp: now + 3600 s,
//   sub, type: "app"}. Options to make a bad one:
//     aud: "<other>"       another audience tag
//     iss: "<other>"       another issuer
//     exp_in: <seconds>    exp = now + this (negative = expired)
//     wrong_key: true      signed by a key the team never published (same kid)
//     kid: "<other>"       a key id the certs do not hold
//     alg: "none"          unsigned token ({"alg":"none"}, empty signature)
//     no_email: true       no email claim
//     via: "cookie"        sent as the cookie CF_Authorization instead of the header
//   AUD is exported to tests as "test-aud-0001" (give it to the Worker as ACCESS_AUD).
//
// D1 stand-in: prepare(sql).bind(...).run()/.all()/.first(col?)/.raw(),
// batch([...]), exec(sql) (one statement per LINE, as real D1). Per request:
//   writes = rows changed (SQLite total_changes), reads = rows handed back,
//   stmts = statements run. full_scans = statements whose query plan reads a
//   whole table ("SCAN <table>"), as in tests/relay_harness.mjs.
// Assets stand-in: env.ASSETS.fetch(request) serves the "assets" map by path
// ("/" -> "/index.html"), 404 otherwise; every path asked is in assets_fetched.

import { DatabaseSync } from "node:sqlite";
import { copyFileSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { generateKeyPairSync, createSign } from "node:crypto";

const TEAM = "testteam";
const ISSUER = `https://${TEAM}.cloudflareaccess.com`;
const CERTS_URL = `${ISSUER}/cdn-cgi/access/certs`;
const AUD = "test-aud-0001";

const fullScans = [];
const counters = { stmts: 0, reads: 0 };

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
    counters.stmts += 1;
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
    counters.reads += rows.length;
    return { success: true, results: rows, meta: {} };
  }
  async first(col) {
    const row = this.prep().get(...this.args);
    if (row === undefined || row === null) return null;
    counters.reads += 1;
    return col === undefined ? row : (row[col] === undefined ? null : row[col]);
  }
  async raw() {
    const rows = this.prep().all(...this.args);
    counters.reads += rows.length;
    return rows.map((r) => Object.values(r));
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
    let count = 0;
    for (const line of sql.split("\n")) {
      if (!line.trim()) continue;
      counters.stmts += 1;
      notePlan(this.db, line, []);
      this.db.exec(line);
      count += 1;
    }
    return { count, duration: 0 };
  }
  changes() {
    return Number(this.db.prepare("SELECT total_changes() AS c").get().c);
  }
  tables() {
    return this.db
      .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
      .all().map((t) => t.name);
  }
  rowsTotal() {
    let n = 0;
    for (const t of this.tables()) {
      n += Number(this.db.prepare(`SELECT COUNT(*) AS c FROM "${t}"`).get().c);
    }
    return n;
  }
  dump() {
    const out = {};
    for (const t of this.tables()) out[t] = this.db.prepare(`SELECT * FROM "${t}"`).all();
    return out;
  }
}

async function loadWorker(path, tag) {
  if (path === "-") return null;
  const dir = mkdtempSync(join(tmpdir(), "cloud_worker_"));
  const copy = join(dir, tag + ".mjs");
  copyFileSync(path, copy);
  const mod = await import(pathToFileURL(copy).href);
  if (!mod.default || typeof mod.default.fetch !== "function") {
    throw new Error(tag + " worker has no default export with fetch()");
  }
  return mod.default;
}

// ---- Cloudflare Access stand-in ----
const good = generateKeyPairSync("rsa", { modulusLength: 2048 });
const rogue = generateKeyPairSync("rsa", { modulusLength: 2048 });
const goodJwk = Object.assign(good.publicKey.export({ format: "jwk" }),
                              { kid: "k1", alg: "RS256", use: "sig" });

const b64u = (buf) => Buffer.from(buf).toString("base64url");

function token(login, nowMs) {
  const now = Math.floor(nowMs / 1000);
  const header = { alg: login.alg || "RS256", kid: login.kid || "k1", typ: "JWT" };
  const payload = {
    aud: [login.aud || AUD],
    iss: login.iss || ISSUER,
    iat: now - 5,
    nbf: now - 5,
    exp: now + (login.exp_in === undefined ? 3600 : login.exp_in),
    sub: "user-0001",
    type: "app",
  };
  if (!login.no_email) payload.email = login.email;
  const head = b64u(JSON.stringify(header)) + "." + b64u(JSON.stringify(payload));
  if (header.alg === "none") return head + ".";
  const signer = createSign("RSA-SHA256");
  signer.update(head);
  const key = login.wrong_key ? rogue.privateKey : good.privateKey;
  return head + "." + b64u(signer.sign(key));
}

let certsFetches = 0;
const otherFetches = [];
globalThis.fetch = async (input) => {
  const url = typeof input === "string" ? input : (input && input.url) || String(input);
  if (url === CERTS_URL) {
    certsFetches += 1;
    return new Response(JSON.stringify({ keys: [goodJwk], public_cert: {}, public_certs: [] }),
                        { status: 200, headers: { "content-type": "application/json" } });
  }
  otherFetches.push(url);
  throw new Error("the harness has no network: " + url);
};

// ---- static assets stand-in ----
const assetsFetched = [];
const TYPES = { html: "text/html; charset=utf-8", js: "text/javascript", glb: "model/gltf-binary",
                png: "image/png", txt: "text/plain" };
function assetsBinding(files) {
  return {
    async fetch(request) {
      const url = new URL(typeof request === "string" ? request : request.url);
      let path = url.pathname;
      assetsFetched.push(path);
      if (path === "/") path = "/index.html";
      if (!Object.prototype.hasOwnProperty.call(files, path)) {
        return new Response("not found", { status: 404 });
      }
      const ext = path.slice(path.lastIndexOf(".") + 1);
      return new Response(files[path], {
        status: 200, headers: { "content-type": TYPES[ext] || "application/octet-stream" },
      });
    },
  };
}

async function asResult(resp) {
  const text = await resp.text();
  let body = text;
  try {
    body = JSON.parse(text);
  } catch (_) {
    // keep the text
  }
  const headers = {};
  resp.headers.forEach((v, k) => { headers[k] = v; });
  return { status: resp.status, body, headers };
}

const realNow = Date.now;

async function main() {
  const [relayPath, cityPath] = process.argv.slice(2);
  const workers = { relay: await loadWorker(relayPath, "relay"), city: await loadWorker(cityPath, "city") };
  const input = JSON.parse(readFileSync(0, "utf8"));
  const d1 = new FakeD1();
  const envs = {
    relay: Object.assign({}, (input.env || {}).relay || {}, { DB: d1 }),
    city: Object.assign({}, (input.env || {}).city || {}, { DB: d1, ASSETS: assetsBinding(input.assets || {}) }),
  };
  const responses = [];
  for (const req of input.requests) {
    const nowMs = req.now === undefined ? realNow() : req.now;
    Date.now = () => nowMs;
    const headers = Object.assign({}, req.headers || {});
    if (req.login) {
      const t = token(req.login, nowMs);
      if (req.login.via === "cookie") headers["Cookie"] = "other=1; CF_Authorization=" + t;
      else headers["Cf-Access-Jwt-Assertion"] = t;
    }
    const init = { method: req.method || "GET", headers };
    if (req.body !== undefined && init.method !== "GET" && init.method !== "HEAD") {
      init.body = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
    }
    const ctx = { waitUntil() {}, passThroughOnException() {} };
    const before = d1.changes();
    counters.stmts = 0;
    counters.reads = 0;
    let result;
    try {
      const worker = workers[req.to || "relay"];
      if (!worker) throw new Error("no worker loaded for: " + req.to);
      const resp = await worker.fetch(new Request("https://cloud.test" + req.path, init),
                                      envs[req.to || "relay"], ctx);
      result = await asResult(resp);
    } catch (err) {
      result = { status: -1, body: String(err && err.stack || err), headers: {} };
    }
    result.writes = d1.changes() - before;
    result.reads = counters.reads;
    result.stmts = counters.stmts;
    responses.push(result);
  }
  Date.now = realNow;
  process.stdout.write(JSON.stringify({
    responses, rows_total: d1.rowsTotal(), full_scans: fullScans,
    certs_fetches: certsFetches, other_fetches: otherFetches,
    assets_fetched: assetsFetched, dump: d1.dump(),
  }) + "\n");
}

await main();
