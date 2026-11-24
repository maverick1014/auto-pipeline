// agent-city-cloud.js — the Agent City page on Cloudflare: behind a login, and the
// owner can talk to a session from it and start an agent from it.
//
// One Cloudflare Worker with static assets, on the team owner's own free
// Cloudflare account. It needs:
//   - the same D1 database the relay writes, bound as `DB`
//   - the static assets (bin/agent-city.html as index.html, and
//     bin/agent-city-assets), bound as `ASSETS`
//   - a plain variable `ACCESS_TEAM`: the Cloudflare Access team
//     ("myteam", "myteam.cloudflareaccess.com" or the full https address)
//   - a plain variable `ACCESS_AUD`: the audience tag of the Access application
// Optional plain variables: `CITY_LANG` ("zh" is the default, or "en") and
// `CITY_ASSET_V` (the ?v= of the asset addresses, default "1").
//
// This Worker reads the table city_view (the relay writes it), the two talk
// tables city_msg and city_chat (the relay writes city_chat) and the order table
// city_order. It writes two things: the owner's messages, the rows of city_msg
// (a new row; the word "not delivered" on a row nobody took; the rows older than
// 7 days of the sender), and the owner's start orders, the rows of city_order
// (a new row; the word "failed" on a row nobody took; the rows older than 7 days
// of the sender). The relay writes the rest of an order, when a machine answers.
// It never writes city_view or city_chat, it makes no call to a machine, and it
// holds no key of any kind: a machine takes its messages and orders at its next
// sync.
//
// Login. Cloudflare Access stands in front of the whole address and sends
// every request on with a signed token. A Worker with static assets gets no
// ctx.access, so this Worker checks the token itself, on every request, before
// it touches an asset or the database. No good token, or Access not set up
// here: 403 {"ok": false, "error": "login required"} and nothing else.
//
// Routes (GET and HEAD, and the two POSTs below; any other method is 405):
//   /                   the page, with its placeholders filled
//   /index.html         the same page
//   /api/feed           this login's city: machines (each with "talk" and
//                       "start": true or false), the picture, the new events.
//                       With ?chat=<window>&cc=<cursor>: also "chat", the open
//                       window of the machine shown (its rows after the cursor,
//                       and the messages still on their way). With a machine
//                       shown: also "orders", its start orders of the last 10
//                       minutes
//   POST /api/chat/send {dev, to, text, cid}: one message of the owner, from
//                       this page only (header, content type, own origin),
//                       with size, shape, rate and "my machine" checks, in the
//                       order of handleSend(). One row, state "sent", or
//                       "undelivered" at once when no machine can take it
//   POST /api/agent/add {dev, terr, oid} or {dev, terr, oid, force}: one start
//                       order of the owner, from this page only, with size,
//                       shape, "my machine", one-at-a-time and rate checks, in
//                       the order of handleAdd(). One row, state "sent", or
//                       "failed" at once when no machine can take it
//   anything else       the assets, untouched (/v1/... and other /api/... are 404)

const CERTS_TTL_MS = 3600 * 1000; // how long the team's keys are kept in memory
const EXTRA_FETCH_GAP_MS = 60 * 1000; // the least time between two extra fetches of the keys
const ASSET_CACHE = "private, max-age=31536000, immutable"; // a versioned asset never changes
const MAX_DEVS = 50; // machines listed for one user
const NO_PICTURE = { people: 0, busy: 0, wait: 0 };

// The talk. All the limits of one owner's messages and of the open window.
const MAX_BODY = 16 * 1024; // bytes of one send request
const MAX_TEXT = 4000; // characters of one message
const OFF_AFTER_MS = 150 * 1000; // a machine that sent nothing for this long is off
const FAST_MS = 5 * 60 * 1000; // the window of the first rate limit ...
const FAST_MAX = 30; // ... this many messages in it
const DAY_MS = 24 * 3600 * 1000; // the window of the second rate limit ...
const DAY_MAX = 300; // ... this many messages in it
const KEEP_MS = 7 * 24 * 3600 * 1000; // a message row is kept this long
const SENT_EXPIRE_MS = 60 * 1000; // a "sent" message nobody took in this time is not delivered
const TAKEN_EXPIRE_MS = 10 * 60 * 1000; // a "taken" one nobody answered for in this time too
const CHAT_ROWS = 200; // the rows of a window that is opened (the newest)
const MSGS_MAX = 50; // the messages on their way shown in one window
const TO_RE = /^(?:s|gov):[A-Za-z0-9_.:-]{1,120}$/; // a session or a governor, never a path
const CID_RE = /^[A-Za-z0-9_-]{16,64}$/;
const SEND_KEYS = ["dev", "to", "text", "cid"]; // the keys of a send body, and no other

// The start orders. All the limits of one owner's orders and of the list shown.
const MAX_ADD_BODY = 1024; // bytes of one add request
const ADD_KEYS = ["dev", "terr", "oid", "force"]; // the keys of an add body, and no other
const ADD_NEEDED = ["dev", "terr", "oid"]; // the ones that must be there
const TERR_RE = /^[0-9a-f]{8}$/; // a territory id, never a path or a name
const OID_RE = /^[A-Za-z0-9_-]{16,64}$/;
const HOUR_MS = 3600 * 1000; // the window of the first order limit ...
const ORDER_HOUR_MAX = 10; // ... this many orders in it
const ORDER_DAY_MAX = 40; // the second limit: this many orders in DAY_MS
const ORDER_SENT_EXPIRE_MS = 60 * 1000; // a "sent" order nobody took in this time failed
const ORDER_SILENT_MS = 180 * 1000; // a "taken" or "opening" one that stayed quiet this long failed
const ORDER_SHOW_MS = 10 * 60 * 1000; // the orders of the last 10 minutes are shown ...
const ORDERS_MAX = 20; // ... the newest of them, this many at most

// The two talk tables: the same lines as the relay's. The one that needs them
// first makes them.
const TALK_TABLES = [
  "CREATE TABLE IF NOT EXISTS city_msg (user TEXT NOT NULL, cid TEXT NOT NULL, dev TEXT NOT NULL, pg TEXT NOT NULL, text TEXT NOT NULL, at INTEGER NOT NULL, state TEXT NOT NULL, why TEXT NOT NULL, PRIMARY KEY (user, cid))",
  "CREATE INDEX IF NOT EXISTS city_msg_dev ON city_msg (user, dev, state)",
  "CREATE TABLE IF NOT EXISTS city_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT NOT NULL, dev TEXT NOT NULL, pg TEXT NOT NULL, k TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, at REAL NOT NULL, ts INTEGER NOT NULL, state TEXT NOT NULL, why TEXT NOT NULL, cid TEXT NOT NULL, UNIQUE (user, dev, k))",
  "CREATE INDEX IF NOT EXISTS city_chat_pg ON city_chat (user, dev, pg, id)",
];

// The order table: the same lines as the relay's. The one that needs it first
// makes it. One row is one click on the add button of the page: `at` is when it
// was placed, `ts` when its state last changed (ms), `info` a small JSON object
// as text.
const ORDER_TABLES = [
  "CREATE TABLE IF NOT EXISTS city_order (user TEXT NOT NULL, oid TEXT NOT NULL, dev TEXT NOT NULL, terr TEXT NOT NULL, force INTEGER NOT NULL, at INTEGER NOT NULL, ts INTEGER NOT NULL, state TEXT NOT NULL, why TEXT NOT NULL, info TEXT NOT NULL, PRIMARY KEY (user, oid))",
  "CREATE INDEX IF NOT EXISTS city_order_dev ON city_order (user, dev, state)",
];

// The team's keys, kept in this Worker instance's memory:
// { host, at, keys: [JWK], imported: Map(kid -> CryptoKey) }
let certsCache = null;
// When the keys were last fetched because a token held a key id not in the list.
let lastExtraFetch = -Infinity;

function json(body, status, extra) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: Object.assign(
      { "content-type": "application/json", "cache-control": "no-store" },
      extra || {}
    ),
  });
}

function loginRequired() {
  return json({ ok: false, error: "login required" }, 403);
}

function isObject(x) {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

// A read of a table that is not there yet found nothing.
function isNoTable(err) {
  return /no such table/i.test(String((err && err.message) || err));
}

// ---- login ----

// "myteam", "myteam.cloudflareaccess.com", "https://myteam.cloudflareaccess.com/"
// -> "myteam.cloudflareaccess.com". Anything else -> "" (the Worker stays closed).
function teamHost(value) {
  if (typeof value !== "string") return "";
  let v = value.trim().toLowerCase();
  v = v.replace(/^https?:\/\//, "").replace(/\/+$/, "");
  if (v.indexOf(".") === -1) v += ".cloudflareaccess.com";
  return /^[a-z0-9-]+\.cloudflareaccess\.com$/.test(v) ? v : "";
}

function cookieValue(header, name) {
  for (const part of header.split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    if (part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return "";
}

// The token: the header Access adds, else the cookie it sets.
function tokenOf(request) {
  const fromHeader = (request.headers.get("Cf-Access-Jwt-Assertion") || "").trim();
  if (fromHeader) return fromHeader;
  return cookieValue(request.headers.get("Cookie") || "", "CF_Authorization");
}

// base64url text -> bytes. Throws on anything that is not base64url.
function b64uBytes(text) {
  if (typeof text !== "string" || !/^[A-Za-z0-9_-]*$/.test(text)) throw new Error("not base64url");
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

function b64uJson(text) {
  return JSON.parse(new TextDecoder().decode(b64uBytes(text)));
}

// Fetch the team's keys and keep them in memory.
async function fetchKeys(host) {
  const now = Date.now();
  const resp = await fetch("https://" + host + "/cdn-cgi/access/certs");
  if (!resp.ok) throw new Error("certs: " + resp.status);
  const data = await resp.json();
  if (!isObject(data) || !Array.isArray(data.keys)) throw new Error("certs: no keys");
  certsCache = { host, at: now, keys: data.keys.filter(isObject), imported: new Map() };
  return certsCache;
}

// The team's keys: from memory for an hour, else fetched. `fresh` is true
// when this call fetched them.
async function teamKeys(host) {
  const now = Date.now();
  if (certsCache && certsCache.host === host && now - certsCache.at < CERTS_TTL_MS) {
    return { cache: certsCache, fresh: false };
  }
  return { cache: await fetchKeys(host), fresh: true };
}

async function verifyKey(cache, kid) {
  if (cache.imported.has(kid)) return cache.imported.get(kid);
  const jwk = cache.keys.find((k) => k.kid === kid && k.kty === "RSA");
  if (!jwk) return null;
  const key = await crypto.subtle.importKey(
    "jwk",
    { kty: "RSA", n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"]
  );
  cache.imported.set(kid, key);
  return key;
}

// The login e-mail (lower case), or "" when there is no good login. Any
// error while checking is "no login".
async function loginEmail(request, env) {
  try {
    const host = teamHost(env.ACCESS_TEAM);
    const aud = typeof env.ACCESS_AUD === "string" ? env.ACCESS_AUD.trim() : "";
    if (!host || !aud) return "";
    const token = tokenOf(request);
    if (!token) return "";
    const parts = token.split(".");
    if (parts.length !== 3) return "";
    const head = b64uJson(parts[0]);
    const claims = b64uJson(parts[1]);
    if (!isObject(head) || !isObject(claims)) return "";
    if (head.alg !== "RS256" || typeof head.kid !== "string") return "";

    // The cheap checks first: a forged token never costs a fetch of the keys.
    const now = Date.now();
    if (claims.iss !== "https://" + host) return "";
    const auds = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
    if (auds.indexOf(aud) === -1) return "";
    if (typeof claims.exp !== "number" || !(claims.exp * 1000 > now)) return "";
    if (typeof claims.nbf === "number" && claims.nbf * 1000 > now + 60000) return "";
    const email = typeof claims.email === "string" ? claims.email.trim().toLowerCase() : "";
    if (!email) return "";

    const got = await teamKeys(host);
    let key = await verifyKey(got.cache, head.kid);
    if (!key && !got.fresh && now - lastExtraFetch >= EXTRA_FETCH_GAP_MS) {
      // Cloudflare may have changed its keys: look once more, but never more
      // than once a minute, so made-up key ids cost one fetch.
      lastExtraFetch = now;
      key = await verifyKey(await fetchKeys(host), head.kid);
    }
    if (!key) return "";
    const ok = await crypto.subtle.verify(
      { name: "RSASSA-PKCS1-v1_5" },
      key,
      b64uBytes(parts[2]),
      new TextEncoder().encode(parts[0] + "." + parts[1])
    );
    return ok ? email : "";
  } catch (err) {
    return "";
  }
}

// ---- the page ----

function onlyLang(value) {
  return value === "en" ? "en" : "zh";
}

function onlyAssetV(value) {
  const v = typeof value === "string" ? value.trim() : "";
  return /^[A-Za-z0-9._-]{1,32}$/.test(v) ? v : "1";
}

function fill(text, name, value) {
  return text.split(name).join(value);
}

async function handlePage(request, env) {
  // Ask for "/", never for "/index.html": the assets answer that with a redirect.
  const asked = new Request(new URL("/", request.url).href, { method: "GET" });
  const resp = await env.ASSETS.fetch(asked);
  if (resp.status !== 200) return resp;
  let html = await resp.text();
  html = fill(html, "__CITY_CLOUD__", "1");
  html = fill(html, "__CITY_TOKEN__", "");
  html = fill(html, "__CITY_LANG__", onlyLang(env.CITY_LANG));
  html = fill(html, "__CITY_ASSET_V__", onlyAssetV(env.CITY_ASSET_V));
  return new Response(html, {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-cache",
      "x-content-type-options": "nosniff",
    },
  });
}

// ---- the feed ----

// A whole number from a query value; anything else is 0 (a first call).
function whole(text) {
  return typeof text === "string" && /^[0-9]{1,15}$/.test(text) ? Number(text) : 0;
}

function countsOf(text) {
  try {
    const c = JSON.parse(text);
    if (!isObject(c)) return Object.assign({}, NO_PICTURE);
    const n = (x) => (Number.isFinite(x) ? x : 0);
    return { people: n(c.people), busy: n(c.busy), wait: n(c.wait) };
  } catch (err) {
    return Object.assign({}, NO_PICTURE);
  }
}

function listOf(text) {
  try {
    const list = JSON.parse(text);
    return Array.isArray(list) ? list : [];
  } catch (err) {
    return [];
  }
}

// The stored events are one batch per line: {"n": <number>, "e": [<message>, ...]}.
// The messages of the batches numbered above `after`, in order.
function eventsAfter(text, after) {
  const out = [];
  if (typeof text !== "string" || !text) return out;
  for (const line of text.split("\n")) {
    if (!line) continue;
    let batch;
    try {
      batch = JSON.parse(line);
    } catch (err) {
      continue;
    }
    if (!isObject(batch) || !Number.isFinite(batch.n) || batch.n <= after || !Array.isArray(batch.e)) continue;
    for (const message of batch.e) out.push(message);
  }
  return out;
}

// This user's machines, the one seen last first, without the big columns. A
// missing table (the relay never ran) is an empty list.
async function machinesOf(db, user) {
  try {
    const { results } = await db
      .prepare("SELECT dev, label, ts, gen, n, counts FROM city_view WHERE user = ? ORDER BY ts DESC LIMIT " + MAX_DEVS)
      .bind(user)
      .all();
    return results || [];
  } catch (err) {
    if (isNoTable(err)) return [];
    throw err;
  }
}

// A flag of a machine: its picture carries "talk": 1 and "start": 1 in its
// counts when the machine has talk on, or start on (the relay puts them there).
function flagOf(text, name) {
  try {
    const c = JSON.parse(text);
    return isObject(c) && c[name] === 1;
  } catch (err) {
    return false;
  }
}

// Does this machine take messages?
function talkOf(text) {
  return flagOf(text, "talk");
}

// Does this machine take start orders?
function startOf(text) {
  return flagOf(text, "start");
}

// The picture part of the feed (step 1): the machines, and the snapshot and
// events of the one shown.
async function pictureOf(url, db, user) {
  const wantDev = url.searchParams.get("dev") || "";
  const gen = whole(url.searchParams.get("gen"));
  const after = whole(url.searchParams.get("after"));

  const machines = await machinesOf(db, user);
  const out = {
    ok: true,
    user,
    now: Date.now(),
    devs: machines.map((m) => ({
      dev: m.dev,
      label: m.label,
      ts: m.ts,
      gen: m.gen,
      counts: countsOf(m.counts),
      talk: talkOf(m.counts),
      start: startOf(m.counts),
    })),
    dev: "",
    gen: 0,
    after: 0,
  };
  const chosen = machines.find((m) => m.dev === wantDev) || machines[0];
  if (!chosen) {
    out.events = [];
    return out;
  }
  out.dev = chosen.dev;

  let needSnap = chosen.gen !== gen;
  let row = null;
  if (!needSnap && after < chosen.n) {
    // Same picture, new batches: read the events only.
    row = await db
      .prepare("SELECT gen, n, events FROM city_view WHERE user = ? AND dev = ? AND gen = ?")
      .bind(user, chosen.dev, chosen.gen)
      .first();
    if (!row) needSnap = true; // the picture was replaced in between
  }
  if (needSnap) {
    row = await db
      .prepare("SELECT gen, n, snap, events FROM city_view WHERE user = ? AND dev = ?")
      .bind(user, chosen.dev)
      .first();
    if (!row) {
      // The machine went away in between: nothing to show, ask again next time.
      out.snap = [];
      out.events = [];
      return out;
    }
    out.gen = row.gen;
    out.after = row.n;
    out.snap = listOf(row.snap);
    out.events = eventsAfter(row.events, 0);
    return out;
  }
  if (row) {
    out.gen = row.gen;
    out.after = row.n;
    out.events = eventsAfter(row.events, after);
    return out;
  }
  out.gen = chosen.gen;
  out.after = chosen.n;
  out.events = [];
  return out;
}

// The open window of the machine shown: its rows after the cursor, and the
// messages of the owner that the machine has no entry for yet (states "sent",
// "taken", "undelivered"; the machine's answer "queued" or "delivered" always
// comes with its row, so those are never listed). `talk` is the machine's talk
// flag, `now` the clock of this poll.
//
// A poll comes every 3 seconds, so it reads through the keys only: the rows of
// the window by (user, dev, window, id), the messages by the index
// (user, dev, state), the machine's row of a message by the unique key
// (user, dev, k) (its row for a cloud message has k = cid). A poll with nothing
// new and nothing too old writes nothing.
async function chatOf(db, user, dev, talk, to, cc, now) {
  const chat = { to, cc, rows: [], msgs: [] };
  let got;
  try {
    got = await db.batch([
      // The newest first, so a window that is just opened gets the 200 newest.
      db
        .prepare(
          "SELECT id, k, kind, text, at, state, why, cid FROM city_chat " +
            "WHERE user = ? AND dev = ? AND pg = ? AND id > ? ORDER BY id DESC LIMIT " + CHAT_ROWS
        )
        .bind(user, dev, to, cc),
      db
        .prepare(
          "SELECT m.cid, m.text, m.at, m.state, m.why FROM city_msg m " +
            "WHERE m.user = ? AND m.dev = ? AND m.state IN ('sent', 'taken', 'undelivered') AND m.pg = ? " +
            "AND NOT EXISTS (SELECT 1 FROM city_chat c WHERE c.user = m.user AND c.dev = m.dev AND c.k = m.cid) " +
            "ORDER BY m.at DESC, m.cid DESC LIMIT " + MSGS_MAX
        )
        .bind(user, dev, to),
    ]);
  } catch (err) {
    if (isNoTable(err)) return chat; // no talk table yet: an empty window
    throw err;
  }

  const rows = (got[0].results || []).slice();
  for (const r of rows) if (r.id > chat.cc) chat.cc = r.id;
  rows.sort((a, b) => a.at - b.at || a.id - b.id);
  chat.rows = rows.map((r) => ({ k: r.k, kind: r.kind, text: r.text, at: r.at, state: r.state, why: r.why, cid: r.cid }));

  // The 50 newest messages, shown oldest first. One nobody took in time is
  // made "not delivered" (stored, so no machine takes it later): one guarded
  // change each, only when there is one.
  const msgs = (got[1].results || []).slice().reverse();
  const tooOld = (state, ms) => msgs.filter((m) => m.state === state && now - m.at >= ms);
  await expire(db, user, dev, to, "sent", talk ? "off" : "talk-off", tooOld("sent", SENT_EXPIRE_MS));
  await expire(db, user, dev, to, "taken", "off", tooOld("taken", TAKEN_EXPIRE_MS));

  chat.msgs = msgs.map((m) => ({ cid: m.cid, text: m.text, at: m.at / 1000, state: m.state, why: m.why }));
  return chat;
}

// Make these messages "not delivered" for `why`, if they are still in `state`.
// Only the rows the statement really changed are marked (in place): a machine
// that took one in between wins, and that message is never shown as not delivered.
async function expire(db, user, dev, to, state, why, rows) {
  if (rows.length === 0) return;
  const marks = rows.map(() => "?").join(", ");
  const { results } = await db
    .prepare(
      "UPDATE city_msg SET state = 'undelivered', why = ? " +
        "WHERE user = ? AND dev = ? AND pg = ? AND state = ? AND cid IN (" + marks + ") RETURNING cid"
    )
    .bind(why, user, dev, to, state, ...rows.map((m) => m.cid))
    .all();
  const changed = new Set((results || []).map((r) => r.cid));
  for (const m of rows) {
    if (!changed.has(m.cid)) continue;
    m.state = "undelivered";
    m.why = why;
  }
}

// The stored info of an order is a small JSON object as text; anything else
// is an empty object.
function infoOf(text) {
  try {
    const info = JSON.parse(text);
    return isObject(info) ? info : {};
  } catch (err) {
    return {};
  }
}

// The start orders of the machine shown that were placed in the last 10 minutes
// (the 20 newest, oldest first). `start` is the machine's start flag, `now` the
// clock of this poll. No order table yet: no orders.
//
// Like the chat, a poll reads through the keys only (user, dev), and a poll with
// nothing too old writes nothing.
async function ordersOf(db, user, dev, start, now) {
  const rows = (
    await rowsOf(
      db,
      "SELECT oid, terr, force, at, ts, state, why, info FROM city_order " +
        "WHERE user = ? AND dev = ? AND at > ? ORDER BY at DESC, oid DESC LIMIT " + ORDERS_MAX,
      user,
      dev,
      now - ORDER_SHOW_MS
    )
  ).reverse();
  await lapseOrders(db, user, dev, start, now, rows);

  return rows.map((r) => ({
    oid: r.oid,
    terr: r.terr,
    force: !!r.force,
    at: r.at,
    ts: r.ts,
    state: r.state,
    why: r.why,
    info: infoOf(r.info),
  }));
}

// An order nobody took in time failed, and so did one that went quiet (`rows`:
// orders of this machine; `start`: its start flag). Stored, so no machine takes
// it later: one guarded change each, only when there is one. The feed and the
// add both use this, so the rule is in one place.
async function lapseOrders(db, user, dev, start, now, rows) {
  const unsent = rows.filter((r) => r.state === "sent" && now - r.at >= ORDER_SENT_EXPIRE_MS);
  const quiet = rows.filter((r) => (r.state === "taken" || r.state === "opening") && now - r.ts >= ORDER_SILENT_MS);
  await expireOrders(db, user, dev, "state = 'sent' AND at <= ?", now - ORDER_SENT_EXPIRE_MS, start ? "off" : "start-off", now, unsent);
  await expireOrders(db, user, dev, "state IN ('taken', 'opening') AND ts <= ?", now - ORDER_SILENT_MS, "silent", now, quiet);
}

// Make these orders "failed" for `why`, if they are still as `guard` says (the
// state, and not changed since `cut`). Only the rows the statement really changed
// are marked (in place): a machine that answered in between wins, and that order
// is never shown as failed.
async function expireOrders(db, user, dev, guard, cut, why, now, rows) {
  if (rows.length === 0) return;
  const marks = rows.map(() => "?").join(", ");
  const { results } = await db
    .prepare(
      "UPDATE city_order SET state = 'failed', why = ?, ts = ? " +
        "WHERE user = ? AND dev = ? AND " + guard + " AND oid IN (" + marks + ") RETURNING oid"
    )
    .bind(why, now, user, dev, cut, ...rows.map((r) => r.oid))
    .all();
  const changed = new Set((results || []).map((r) => r.oid));
  for (const r of rows) {
    if (!changed.has(r.oid)) continue;
    r.state = "failed";
    r.why = why;
    r.ts = now;
  }
}

async function handleFeed(url, env, user) {
  const out = await pictureOf(url, env.DB, user);
  if (out.dev) {
    const shown = out.devs.find((d) => d.dev === out.dev);
    const to = url.searchParams.get("chat");
    if (typeof to === "string" && TO_RE.test(to)) {
      out.chat = await chatOf(env.DB, user, out.dev, !!(shown && shown.talk), to, whole(url.searchParams.get("cc")), out.now);
    }
    out.orders = await ordersOf(env.DB, user, out.dev, !!(shown && shown.start), out.now);
  }
  return json(out);
}

// ---- the owner's message ----

// A read that gives one row, or null when there is none (or no table yet).
async function rowOf(db, sql, ...args) {
  try {
    return await db.prepare(sql).bind(...args).first();
  } catch (err) {
    if (isNoTable(err)) return null;
    throw err;
  }
}

// A read that gives all its rows, or none when there is no table yet.
async function rowsOf(db, sql, ...args) {
  try {
    const { results } = await db.prepare(sql).bind(...args).all();
    return (results || []).slice();
  } catch (err) {
    if (isNoTable(err)) return [];
    throw err;
  }
}

// The body of a request as text, or null when it is longer than `max` bytes.
async function bodyText(request, max) {
  if (Number(request.headers.get("Content-Length")) > max) return null;
  if (!request.body) return "";
  const reader = request.body.getReader();
  const parts = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > max) {
      await reader.cancel();
      return null;
    }
    parts.push(value);
  }
  const all = new Uint8Array(size);
  let at = 0;
  for (const part of parts) {
    all.set(part, at);
    at += part.length;
  }
  return new TextDecoder().decode(all);
}

function refuse(error, status) {
  return json({ ok: false, error }, status);
}

// Does the request come from this page? A page of another site cannot set
// these: the header, the content type and the origin of the request's own URL.
function fromThisPage(request, url) {
  const ctype = (request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  return (
    request.headers.get("X-City-Page") === "1" &&
    ctype === "application/json" &&
    request.headers.get("Origin") === url.origin
  );
}

// POST /api/chat/send {dev, to, text, cid}: a route that acts. The checks run in
// this order, and nothing is written before the last one has passed.
async function handleSend(request, env, user) {
  const db = env.DB;
  const url = new URL(request.url);

  // Only this page can send.
  if (!fromThisPage(request, url)) return refuse("bad origin", 403);

  const raw = await bodyText(request, MAX_BODY);
  if (raw === null) return refuse("too big", 413);
  let body = null;
  try {
    body = JSON.parse(raw);
  } catch (err) {
    body = null;
  }
  // A JSON object with these keys and no other: nothing unknown is ignored.
  if (!isObject(body) || Object.keys(body).some((key) => SEND_KEYS.indexOf(key) === -1)) return refuse("body", 400);

  const { text, cid, to } = body;
  if (typeof text !== "string" || text.length > MAX_TEXT || text.trim() === "") return refuse("text", 400);
  if (typeof cid !== "string" || !CID_RE.test(cid)) return refuse("cid", 400);
  if (typeof to !== "string" || !TO_RE.test(to)) return refuse("to", 400);

  // The machine must be one of this login.
  const dev = typeof body.dev === "string" ? body.dev : "";
  const machine = dev ? await rowOf(db, "SELECT ts, counts FROM city_view WHERE user = ? AND dev = ?", user, dev) : null;
  if (!machine) return refuse("dev", 404);

  // The same message again: say what became of the first one, store nothing.
  const same = await rowOf(db, "SELECT state, why FROM city_msg WHERE user = ? AND cid = ?", user, cid);
  if (same) return json({ ok: true, cid, state: same.state, why: same.why });

  const now = Date.now();
  const rate = await rowOf(
    db,
    "SELECT COUNT(*) AS day, COALESCE(SUM(at > ?), 0) AS fast FROM city_msg WHERE user = ? AND at > ?",
    now - FAST_MS,
    user,
    now - DAY_MS
  );
  if (rate && rate.fast >= FAST_MAX) return refuse("too fast", 429);
  if (rate && rate.day >= DAY_MAX) return refuse("too many today", 429);

  // Be honest at once when no machine can take it.
  let state = "sent";
  let why = "";
  if (now - machine.ts > OFF_AFTER_MS) {
    state = "undelivered";
    why = "off";
  } else if (!talkOf(machine.counts)) {
    state = "undelivered";
    why = "talk-off";
  }

  await db.batch(TALK_TABLES.map((line) => db.prepare(line)));
  await db.batch([
    db.prepare("DELETE FROM city_msg WHERE user = ? AND at < ?").bind(user, now - KEEP_MS),
    db
      .prepare("INSERT OR IGNORE INTO city_msg (user, cid, dev, pg, text, at, state, why) VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
      .bind(user, cid, dev, to, text, now, state, why),
  ]);
  return json({ ok: true, cid, state, why });
}

// ---- the owner's start order ----

// POST /api/agent/add {dev, terr, oid} or {dev, terr, oid, force}: the second
// route that acts. The checks run in this order, and nothing is written before
// the last one has passed. The body names a machine and a territory id, never a
// path, a name or a command: the machine opens the folder it knows by that id.
async function handleAdd(request, env, user) {
  const db = env.DB;
  const url = new URL(request.url);

  // Only this page can order.
  if (!fromThisPage(request, url)) return refuse("bad origin", 403);

  const raw = await bodyText(request, MAX_ADD_BODY);
  if (raw === null) return refuse("too big", 413);
  let body = null;
  try {
    body = JSON.parse(raw);
  } catch (err) {
    body = null;
  }
  // A JSON object with these keys and no other: nothing unknown is ignored.
  if (!isObject(body) || Object.keys(body).some((key) => ADD_KEYS.indexOf(key) === -1)) return refuse("body", 400);
  const has = (key) => Object.prototype.hasOwnProperty.call(body, key);
  if (!ADD_NEEDED.every(has)) return refuse("body", 400);

  const { terr, oid } = body;
  if (typeof terr !== "string" || !TERR_RE.test(terr)) return refuse("terr", 400);
  if (typeof oid !== "string" || !OID_RE.test(oid)) return refuse("oid", 400);
  if (has("force") && typeof body.force !== "boolean") return refuse("force", 400);
  const force = body.force === true ? 1 : 0;

  // The machine must be one of this login.
  const dev = typeof body.dev === "string" ? body.dev : "";
  const machine = dev ? await rowOf(db, "SELECT ts, counts FROM city_view WHERE user = ? AND dev = ?", user, dev) : null;
  if (!machine) return refuse("dev", 404);

  // The same order again: say what became of the first one, store nothing.
  const again = await storedOrder(db, user, oid);
  if (again) return again;

  // An order of this repo that is past its time failed (stored): a dead order
  // never locks the repo. Only this repo's orders are touched.
  const now = Date.now();
  const live = await rowsOf(
    db,
    "SELECT oid, at, ts, state FROM city_order WHERE user = ? AND dev = ? AND terr = ? AND state IN ('sent', 'taken', 'opening') " +
      "ORDER BY at DESC, oid DESC",
    user,
    dev,
    terr
  );
  await lapseOrders(db, user, dev, startOf(machine.counts), now, live);

  // One order at a time for a repo: a double click opens one session.
  const busy = live.find((r) => r.state !== "failed");
  if (busy) return json({ ok: false, error: "busy", oid: busy.oid }, 409);

  // Every order counts, a confirm and a failed one too.
  const rate = await rowOf(
    db,
    "SELECT COUNT(*) AS day, COALESCE(SUM(at > ?), 0) AS hour FROM city_order WHERE user = ? AND at > ?",
    now - HOUR_MS,
    user,
    now - DAY_MS
  );
  if (rate && rate.hour >= ORDER_HOUR_MAX) {
    // The wait ends when the 10th newest of the hour is an hour old.
    const edge = await rowOf(
      db,
      "SELECT at FROM city_order WHERE user = ? AND at > ? ORDER BY at DESC LIMIT 1 OFFSET " + (ORDER_HOUR_MAX - 1),
      user,
      now - HOUR_MS
    );
    const wait = edge ? Math.max(1, Math.ceil((edge.at + HOUR_MS - now) / 1000)) : 1;
    return json({ ok: false, error: "too many this hour", wait }, 429);
  }
  if (rate && rate.day >= ORDER_DAY_MAX) return refuse("too many today", 429);

  // Be honest at once when no machine can take it.
  let state = "sent";
  let why = "";
  if (now - machine.ts > OFF_AFTER_MS) {
    state = "failed";
    why = "off";
  } else if (!startOf(machine.counts)) {
    state = "failed";
    why = "start-off";
  }

  await db.batch(ORDER_TABLES.map((line) => db.prepare(line)));
  await db.prepare("DELETE FROM city_order WHERE user = ? AND at < ?").bind(user, now - KEEP_MS).run();

  // The order is stored by ONE statement that stores it only when no order of
  // this repo is in flight, so two requests at the same moment store one order.
  const made = await db
    .prepare(
      "INSERT OR IGNORE INTO city_order (user, oid, dev, terr, force, at, ts, state, why, info) " +
        "SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ? " +
        "WHERE NOT EXISTS (SELECT 1 FROM city_order WHERE user = ? AND dev = ? AND terr = ? AND state IN ('sent', 'taken', 'opening'))"
    )
    .bind(user, oid, dev, terr, force, now, now, state, why, "{}", user, dev, terr)
    .run();
  if (made.meta && made.meta.changes === 0) {
    // Nothing stored: the same order came in between (say what became of it),
    // or one of this repo is in flight now (busy, with its oid).
    const first = await storedOrder(db, user, oid);
    if (first) return first;
    const held = await rowOf(
      db,
      "SELECT oid FROM city_order WHERE user = ? AND dev = ? AND terr = ? AND state IN ('sent', 'taken', 'opening') " +
        "ORDER BY at DESC, oid DESC LIMIT 1",
      user,
      dev,
      terr
    );
    return json({ ok: false, error: "busy", oid: held ? held.oid : "" }, 409);
  }
  return json({ ok: true, oid, state, why, info: {} });
}

// The answer for an order of this user that is already stored (what became of
// it), or null when there is none.
async function storedOrder(db, user, oid) {
  const row = await rowOf(db, "SELECT state, why, info FROM city_order WHERE user = ? AND oid = ?", user, oid);
  return row ? json({ ok: true, oid, state: row.state, why: row.why, info: infoOf(row.info) }) : null;
}

// ---- routes ----

export default {
  async fetch(request, env, ctx) {
    // The login check comes first, before any asset or database call.
    const user = await loginEmail(request, env);
    if (!user) return loginRequired();

    const sending = request.method === "POST" && new URL(request.url).pathname === "/api/chat/send";
    const adding = request.method === "POST" && new URL(request.url).pathname === "/api/agent/add";
    if (request.method !== "GET" && request.method !== "HEAD" && !sending && !adding) {
      return json({ ok: false, error: "view only" }, 405, { allow: "GET, HEAD" });
    }

    try {
      const url = new URL(request.url);
      const path = url.pathname;
      if (sending) return await handleSend(request, env, user);
      if (adding) return await handleAdd(request, env, user);
      if (path === "/" || path === "/index.html") return await handlePage(request, env);
      if (path === "/api/feed") return await handleFeed(url, env, user);
      if (path === "/v1" || path.startsWith("/v1/") || path === "/api" || path.startsWith("/api/")) {
        return json({ ok: false, error: "not found" }, 404);
      }
      const resp = await env.ASSETS.fetch(request);
      // An address with this Worker's version in ?v= never changes: the
      // browser may keep it. Any other answer is passed on untouched.
      if (resp.status === 200 && url.searchParams.get("v") === onlyAssetV(env.CITY_ASSET_V)) {
        const headers = new Headers(resp.headers);
        headers.set("cache-control", ASSET_CACHE);
        return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers });
      }
      return resp;
    } catch (err) {
      return json({ ok: false, error: "server error" }, 500);
    }
  },
};
