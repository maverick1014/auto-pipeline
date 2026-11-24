// agent-city-relay.js — the team relay for agent-city.
//
// One Cloudflare Worker, on the team owner's own free Cloudflare account.
// Paste this whole file into the Cloudflare dashboard Worker editor. It
// needs:
//   - a D1 database bound as `DB`
//   - a secret named `TEAM_KEY` (the shared team password)
//
// It holds the last 300 seconds of "lines" any joined machine sent, so a
// newly joined machine can catch up on what the others just did. It never
// keeps a history: old rows are deleted as they age out, and a sync with no
// lines writes nothing at all.
//
// Optional: a plain variable named `CITY_USER` (the owner's e-mail) turns the
// cloud page on. A sync may then carry a "view": that machine's city picture,
// kept in one row per user + machine (table city_view) for the cloud page to
// read. Unset or blank, the view is ignored and the relay works as above.
//
// Optional, talk from the cloud page: a secret named `TALK_KEY` (a password of
// its own; the team key is never a talk key). It works only with CITY_USER set.
// A machine that sends that key in the header X-City-Talk may add a "talk" to
// its sync: the chat rows it copies up (table city_chat), and its answers for
// the messages the owner typed on the cloud page (table city_msg). Only the
// City Worker makes a message row; the relay only changes its state. The reply
// then carries "talk": {"state": "on", "msgs": [...]}, the messages waiting
// for that machine (10 a sync at most). A sync without the header is answered
// as above, and no talk table is made for it.
//
// Starting an agent from the cloud page rides the same talk (no new secret). A
// talk-on sync whose talk has a "start" object also gets the orders the owner
// placed with the add-agent button (table city_order): the machine's answers in
// "start": {"acks": [...]} change the state of its orders, and the reply's talk
// then carries "start": {"state": "on", "orders": [...]}, the orders waiting for
// that machine (3 a sync at most). "start": {"off": true} says starting is off
// there. Only the City Worker makes an order row; the relay only changes its
// state. A talk without "start" is answered as above, and no order table is
// made for it.

const WINDOW_MS = 300_000; // how long a line is handed out for
const MAX_LINES = 200; // lines allowed in one sync
const MAX_BODY_BYTES = 256 * 1024; // body size cap
const MAX_RETURN = 500; // lines handed back in one reply, newest kept
const MAX_EVENTS = 500; // page messages allowed in one view
const CITY_KEEP_MS = 24 * 3600 * 1000; // a machine not heard from this long is dropped

const TALK_MAX_ACKS = 50; // answers read from one sync
const TALK_MAX_CHAT = 20; // chat rows read from one sync
const TALK_MAX_TEXT = 8000; // characters kept of a chat row's text
const TALK_MAX_DOWN = 10; // messages handed down in one reply
const TALK_SENT_MS = 60_000; // a message nobody took in this time is not delivered
const TALK_TAKEN_MS = 600_000; // a message taken but never answered, same
const TALK_KEEP_MS = 7 * 24 * 3600 * 1000; // chat rows older than this leave
const TALK_KEEP_ROWS = 200; // chat rows kept for one conversation

const START_MAX_ACKS = 20; // order answers read from one sync
const START_MAX_DOWN = 3; // orders handed down in one reply, and taken at once
const START_MAX_NAME = 80; // characters kept of an agent's name in an answer
const START_MAX_DETAIL = 200; // characters kept of the detail in an answer
const START_SENT_MS = 60_000; // an order nobody took in this time failed (off)
const START_TAKEN_MS = 180_000; // an order taken but with no word from the machine in this time failed (silent)

// Each stored row (one batch) claims a block of SEQ_STEP seq numbers, the
// row's id times SEQ_STEP, plus the line's place in the batch. SEQ_STEP
// must stay bigger than MAX_LINES so two batches never share a number, and
// a later batch's block always sits above every earlier one's.
const SEQ_STEP = 1000;

// D1 runs exec() one line at a time, so every statement here is one line.
const SETUP_SQL = `CREATE TABLE IF NOT EXISTS relay_batch (id INTEGER PRIMARY KEY AUTOINCREMENT, dev TEXT NOT NULL, ts INTEGER NOT NULL, n INTEGER NOT NULL, lines TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS relay_batch_ts ON relay_batch (ts);`;

// Only run when the cloud page is on. One line: the statement is one line.
const CITY_SQL = "CREATE TABLE IF NOT EXISTS city_view (user TEXT NOT NULL, dev TEXT NOT NULL, label TEXT NOT NULL, ts INTEGER NOT NULL, gen INTEGER NOT NULL, n INTEGER NOT NULL, counts TEXT NOT NULL, snap TEXT NOT NULL, events TEXT NOT NULL, PRIMARY KEY (user, dev))";

// Only run on a talk sync. The City Worker makes the same four tables with the
// same four lines (IF NOT EXISTS), so either Worker may be the first to need them.
const MSG_SQL = "CREATE TABLE IF NOT EXISTS city_msg (user TEXT NOT NULL, cid TEXT NOT NULL, dev TEXT NOT NULL, pg TEXT NOT NULL, text TEXT NOT NULL, at INTEGER NOT NULL, state TEXT NOT NULL, why TEXT NOT NULL, PRIMARY KEY (user, cid))";
const MSG_INDEX_SQL = "CREATE INDEX IF NOT EXISTS city_msg_dev ON city_msg (user, dev, state)";
const CHAT_SQL = "CREATE TABLE IF NOT EXISTS city_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT NOT NULL, dev TEXT NOT NULL, pg TEXT NOT NULL, k TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, at REAL NOT NULL, ts INTEGER NOT NULL, state TEXT NOT NULL, why TEXT NOT NULL, cid TEXT NOT NULL, UNIQUE (user, dev, k))";
const CHAT_INDEX_SQL = "CREATE INDEX IF NOT EXISTS city_chat_pg ON city_chat (user, dev, pg, id)";
const TALK_SQL = [MSG_SQL, MSG_INDEX_SQL, CHAT_SQL, CHAT_INDEX_SQL].join("\n");

// Only run on a start sync (a talk sync whose talk has "start"). The City Worker
// makes the same two tables with the same two lines (IF NOT EXISTS). One row is
// one click on the add-agent button: at = placed, ts = last change of state (ms).
const ORDER_SQL = "CREATE TABLE IF NOT EXISTS city_order (user TEXT NOT NULL, oid TEXT NOT NULL, dev TEXT NOT NULL, terr TEXT NOT NULL, force INTEGER NOT NULL, at INTEGER NOT NULL, ts INTEGER NOT NULL, state TEXT NOT NULL, why TEXT NOT NULL, info TEXT NOT NULL, PRIMARY KEY (user, oid))";
const ORDER_INDEX_SQL = "CREATE INDEX IF NOT EXISTS city_order_dev ON city_order (user, dev, state)";
const START_SQL = [ORDER_SQL, ORDER_INDEX_SQL].join("\n");

// The free plan allows 50 statements a request, so lists of rows go to SQL as
// ONE json text (?3 or ?4 below) and a statement reads them with json_each:
// one statement for any number of rows. ?1 is the user, ?2 the machine.

// Answers (?3 = [{cid, state, why}]). Only a message of this machine that is
// 'taken' or 'queued' changes, and only when the answer says something new.
const ACKS_SQL =
  "UPDATE city_msg SET state = json_extract(a.value, '$.state'), why = json_extract(a.value, '$.why') FROM json_each(?3) a " +
  "WHERE city_msg.user = ?1 AND city_msg.dev = ?2 AND city_msg.state IN ('taken', 'queued') AND city_msg.cid = json_extract(a.value, '$.cid') " +
  "AND (city_msg.state != json_extract(a.value, '$.state') OR city_msg.why != json_extract(a.value, '$.why'))";

// Chat rows (?3 = [{k, state, why}]): a row whose state or why changed leaves ...
const CHAT_DROP_SQL =
  "DELETE FROM city_chat WHERE id IN (SELECT c.id FROM json_each(?3) j JOIN city_chat c ON c.user = ?1 AND c.dev = ?2 AND c.k = json_extract(j.value, '$.k') " +
  "WHERE c.state != json_extract(j.value, '$.state') OR c.why != json_extract(j.value, '$.why'))";
// ... and the insert (?3 = now, ?4 = the rows) puts it back with a new id.
// Rows that did not change are ignored, so they keep their id and write nothing.
const CHAT_PUT_SQL =
  "INSERT OR IGNORE INTO city_chat (user, dev, pg, k, kind, text, at, ts, state, why, cid) " +
  "SELECT ?1, ?2, json_extract(value, '$.to'), json_extract(value, '$.k'), json_extract(value, '$.kind'), json_extract(value, '$.text'), " +
  "json_extract(value, '$.at'), ?3, json_extract(value, '$.state'), json_extract(value, '$.why'), json_extract(value, '$.cid') FROM json_each(?4)";
// Rows of one user older than 7 days (?2 = the cut-off) leave.
const CHAT_OLD_SQL = "DELETE FROM city_chat WHERE user = ?1 AND ts <= ?2";
// Each conversation touched (?3 = its names) keeps its newest rows only.
const CHAT_TRIM_SQL =
  "DELETE FROM city_chat WHERE id IN (SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY pg ORDER BY at DESC, id DESC) AS rn " +
  `FROM city_chat WHERE user = ?1 AND dev = ?2 AND pg IN (SELECT value FROM json_each(?3))) WHERE rn > ${TALK_KEEP_ROWS})`;

// Messages going down (?1 user, ?2 machine, ?3 now). Each change of state is
// one guarded UPDATE: a message that became 'undelivered' is never taken later.
const DOWN_EXPIRE_SQL =
  "UPDATE city_msg SET state = 'undelivered', why = 'off' WHERE user = ?1 AND dev = ?2 AND state IN ('sent', 'taken') " +
  `AND ?3 - at >= CASE state WHEN 'sent' THEN ${TALK_SENT_MS} ELSE ${TALK_TAKEN_MS} END`;
// The oldest 'sent' messages become 'taken', so that no more than 10 are taken
// at once; the rest wait as 'sent' for the next sync.
const DOWN_TAKE_SQL =
  "UPDATE city_msg SET state = 'taken' WHERE user = ?1 AND dev = ?2 AND state = 'sent' AND cid IN (SELECT cid FROM city_msg WHERE user = ?1 AND dev = ?2 AND state = 'sent' " +
  `ORDER BY at, cid LIMIT MAX(0, ${TALK_MAX_DOWN} - (SELECT COUNT(*) FROM city_msg WHERE user = ?1 AND dev = ?2 AND state = 'taken')))`;
const DOWN_LIST_SQL =
  `SELECT cid, pg, text, at FROM city_msg WHERE user = ?1 AND dev = ?2 AND state = 'taken' ORDER BY at, cid LIMIT ${TALK_MAX_DOWN}`;

// Orders (the same ?1 user, ?2 machine). Answers (?3 = [{oid, state, why, info}],
// ?4 = now). Only an order of this machine that is 'taken' or 'opening'
// changes, and only when the answer says something new. info is already JSON text.
const ORDER_ACKS_SQL =
  "UPDATE city_order SET state = json_extract(a.value, '$.state'), why = json_extract(a.value, '$.why'), info = json_extract(a.value, '$.info'), ts = ?4 FROM json_each(?3) a " +
  "WHERE city_order.user = ?1 AND city_order.dev = ?2 AND city_order.state IN ('taken', 'opening') AND city_order.oid = json_extract(a.value, '$.oid') " +
  "AND (city_order.state != json_extract(a.value, '$.state') OR city_order.why != json_extract(a.value, '$.why') OR city_order.info != json_extract(a.value, '$.info'))";

// Orders going down (?3 = now). Each change of state is one guarded UPDATE: an
// order that became 'failed' is never taken later. One that was not taken in
// time failed (off); one taken or opening with no word for too long failed (silent).
const ORDER_EXPIRE_SQL =
  "UPDATE city_order SET why = CASE state WHEN 'sent' THEN 'off' ELSE 'silent' END, state = 'failed', ts = ?3 WHERE user = ?1 AND dev = ?2 AND state IN ('sent', 'taken', 'opening') " +
  `AND ?3 - CASE state WHEN 'sent' THEN at ELSE ts END >= CASE state WHEN 'sent' THEN ${START_SENT_MS} ELSE ${START_TAKEN_MS} END`;
// The oldest 'sent' orders become 'taken', so that no more than 3 are taken at
// once; the rest wait as 'sent' for the next sync.
const ORDER_TAKE_SQL =
  "UPDATE city_order SET state = 'taken', ts = ?3 WHERE user = ?1 AND dev = ?2 AND state = 'sent' AND oid IN (SELECT oid FROM city_order WHERE user = ?1 AND dev = ?2 AND state = 'sent' " +
  `ORDER BY at, oid LIMIT MAX(0, ${START_MAX_DOWN} - (SELECT COUNT(*) FROM city_order WHERE user = ?1 AND dev = ?2 AND state = 'taken')))`;
const ORDER_LIST_SQL =
  `SELECT oid, terr, force, at FROM city_order WHERE user = ?1 AND dev = ?2 AND state = 'taken' ORDER BY at, oid LIMIT ${START_MAX_DOWN}`;

// Starting turned off on the machine (?3 = now): what waits is failed ('opening'
// is left, its terminal is opening) ...
const ORDER_OFF_SQL = "UPDATE city_order SET state = 'failed', why = 'start-off', ts = ?3 WHERE user = ?1 AND dev = ?2 AND state IN ('sent', 'taken')";
// ... and its picture loses the start flag.
const START_FLAG_OFF_SQL = "UPDATE city_view SET counts = json_remove(counts, '$.start') WHERE user = ? AND dev = ? AND json_extract(counts, '$.start') IS NOT NULL";

// What the talk keys and values may be.
const TALK_KEY_RE = /^[A-Za-z0-9_.:-]{1,64}$/;
const TALK_KINDS = ["prompt", "reply", "owner"];
const TALK_ANSWERS = ["queued", "delivered", "undelivered"];
const TALK_WHY = ["ended", "not-listening", "off", "refused", "flood"];

// What the start answers may be.
const START_ANSWERS = ["opening", "opened", "cap", "failed"];
const START_WHY = ["no-orca", "gone", "orca", "late", "busy", "flood", "restart", "refused", "off"];
const START_ROLES = ["main", "helper"];

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: { "content-type": "application/json" },
  });
}

// Constant-time compare: same length check, then XOR every byte, so a
// wrong key never leaks timing information about where it stopped matching.
function sameKey(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function checkAuth(request, teamKey) {
  const header = request.headers.get("Authorization") || "";
  if (!header.startsWith("Bearer ")) return false;
  return sameKey(header.slice("Bearer ".length), teamKey);
}

function isObject(x) {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

function isCount(x) {
  return Number.isSafeInteger(x) && x >= 0;
}

// JSON text that never holds a line-break character of any kind, so the
// stored event batches can be split on lines safely.
function oneLine(value) {
  // U+2028 and U+2029 count as line breaks to some readers; write them escaped.
  return JSON.stringify(value).split(String.fromCharCode(0x2028)).join("\\u2028").split(String.fromCharCode(0x2029)).join("\\u2029");
}

// A list of page messages (snap or events), or the error Response.
function readMessages(list, name) {
  if (!Array.isArray(list) || !list.every(isObject)) {
    return { error: json({ ok: false, error: "view." + name + " must be a list of objects" }, 400) };
  }
  return { list };
}

// Check a "view" before anything is stored. Returns {view}, with counts
// reduced to the three numbers the page uses, or the error Response.
function readView(view) {
  if (!isObject(view)) {
    return { error: json({ ok: false, error: "view must be an object" }, 400) };
  }
  const { label, gen, counts, snap, events } = view;
  if (typeof label !== "string" || label.length < 1 || label.length > 64) {
    return { error: json({ ok: false, error: "view.label must be 1..64 chars" }, 400) };
  }
  if (!Number.isSafeInteger(gen) || gen < 1) {
    return { error: json({ ok: false, error: "view.gen must be a whole number, 1 or more" }, 400) };
  }
  if (!isObject(counts) || !isCount(counts.people) || !isCount(counts.busy) || !isCount(counts.wait)) {
    return { error: json({ ok: false, error: "view.counts must be people, busy, wait: whole numbers" }, 400) };
  }
  const out = { label, gen, counts: { people: counts.people, busy: counts.busy, wait: counts.wait } };
  if (snap !== undefined) {
    const got = readMessages(snap, "snap");
    if (got.error) return got;
    out.snap = got.list;
  }
  if (events !== undefined) {
    if (Array.isArray(events) && events.length > MAX_EVENTS) {
      return { error: json({ ok: false, error: "too many events, 500 max" }, 413) };
    }
    const got = readMessages(events, "events");
    if (got.error) return got;
    out.events = got.list;
  }
  return { view: out };
}

// Turn the raw request body text into a validated {dev, after, lines, view,
// talk}, or return the error Response to send straight back. The view is only
// read when the cloud page is on; otherwise it is ignored, bad or not. The
// talk is handed on as it came: readTalk cleans it, and only for a talk sync.
function readSync(text, cityOn) {
  if (new TextEncoder().encode(text).length > MAX_BODY_BYTES) {
    return { error: json({ ok: false, error: "body too big" }, 413) };
  }
  let body;
  try {
    body = JSON.parse(text);
  } catch (err) {
    return { error: json({ ok: false, error: "body is not JSON" }, 400) };
  }
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    return { error: json({ ok: false, error: "body is not an object" }, 400) };
  }
  const { dev, after, lines } = body;
  if (typeof dev !== "string" || dev.length < 1 || dev.length > 64) {
    return { error: json({ ok: false, error: "dev must be 1..64 chars" }, 400) };
  }
  if (typeof after !== "number" || !Number.isFinite(after)) {
    return { error: json({ ok: false, error: "after must be a number" }, 400) };
  }
  if (!Array.isArray(lines)) {
    return { error: json({ ok: false, error: "lines must be a list" }, 400) };
  }
  for (const line of lines) {
    if (typeof line !== "object" || line === null || Array.isArray(line)) {
      return { error: json({ ok: false, error: "each line must be an object" }, 400) };
    }
  }
  if (lines.length > MAX_LINES) {
    return { error: json({ ok: false, error: "too many lines, 200 max" }, 413) };
  }
  let view;
  if (cityOn && body.view !== undefined) {
    const got = readView(body.view);
    if (got.error) return got;
    view = got.view;
  }
  return { dev, after, lines, view, talk: body.talk };
}

// The state of talk for this sync, from the header and the relay's settings:
// "none" (no header: talk is not asked for), "off" (the relay has no CITY_USER
// or no TALK_KEY), "refused" (wrong key) or "on". The key is compared like the
// team key; a blank TALK_KEY is the same as none.
function talkMode(request, env, user) {
  const header = request.headers.get("X-City-Talk");
  if (header === null) return "none";
  if (user === "" || typeof env.TALK_KEY !== "string" || env.TALK_KEY.trim() === "") return "off";
  return sameKey(header, env.TALK_KEY) ? "on" : "refused";
}

// Why an answer gives for a message that did not arrive; anything else is dropped.
function talkWhy(why) {
  return TALK_WHY.includes(why) ? why : "";
}

// One chat row from a machine, cleaned, or null when it is not a good row.
function readChatRow(r) {
  if (!isObject(r)) return null;
  const { k, to, kind, text, at } = r;
  const state = r.state === undefined ? "" : r.state;
  const cid = r.cid === undefined ? "" : r.cid;
  if (typeof k !== "string" || !TALK_KEY_RE.test(k)) return null;
  if (typeof to !== "string" || to.length < 1 || to.length > 160) return null;
  if (!TALK_KINDS.includes(kind) || typeof text !== "string") return null;
  if (typeof at !== "number" || !Number.isFinite(at)) return null;
  if (state !== "" && !TALK_ANSWERS.includes(state)) return null;
  if (typeof cid !== "string" || cid.length > 64) return null;
  // The City Worker finds a message's row by its key (user, dev, k), so a row
  // that names a message must be keyed by that message's cid.
  if (cid !== "" && k !== cid) return null;
  // Cut by characters, not by UTF-16 units, so no pair is split in the middle.
  const kept = text.length > TALK_MAX_TEXT ? Array.from(text).slice(0, TALK_MAX_TEXT).join("") : text;
  return { k, to, kind, text: kept, at, state, why: talkWhy(r.why), cid };
}

// Cut by characters, not by UTF-16 units, so no pair is split in the middle.
function cutText(text, max) {
  return text.length > max ? Array.from(text).slice(0, max).join("") : text;
}

// The info of an order answer as JSON text: only the known keys are kept, and
// "{}" when nothing is kept or it is no object.
function readStartInfo(raw) {
  const info = {};
  if (isObject(raw)) {
    if (typeof raw.name === "string") info.name = cutText(raw.name, START_MAX_NAME);
    if (START_ROLES.includes(raw.role)) info.role = raw.role;
    for (const key of ["ram", "cpu", "max"]) {
      if (isCount(raw[key])) info[key] = raw[key];
    }
    if (typeof raw.detail === "string") info.detail = cutText(raw.detail, START_MAX_DETAIL);
  }
  return JSON.stringify(info);
}

// A "start" from a machine, cleaned: {off, acks}. A bad answer is skipped and
// the rest is kept; it never fails the sync. One answer per order (the last one wins).
function readStart(raw) {
  const out = { off: false, acks: [] };
  if (raw.off === true) {
    out.off = true;
    return out;
  }
  if (Array.isArray(raw.acks)) {
    const acks = new Map();
    for (const a of raw.acks.slice(0, START_MAX_ACKS)) {
      if (!isObject(a) || typeof a.oid !== "string" || a.oid.length < 1 || a.oid.length > 64) continue;
      if (!START_ANSWERS.includes(a.state)) continue;
      const why = START_WHY.includes(a.why) ? a.why : "";
      acks.set(a.oid, { oid: a.oid, state: a.state, why, info: readStartInfo(a.info) });
    }
    out.acks = [...acks.values()];
  }
  return out;
}

// A "talk" from a machine, cleaned: {off, acks, chat, start}. A bad answer or a bad
// row is skipped and the rest is kept; it never fails the sync. One answer per
// message and one row per key (the last one wins). start is null unless the
// talk has a "start" object.
function readTalk(raw) {
  const out = { off: false, acks: [], chat: [], start: null };
  if (!isObject(raw)) return out;
  if (raw.off === true) {
    out.off = true;
    return out;
  }
  if (Array.isArray(raw.acks)) {
    const acks = new Map();
    for (const a of raw.acks.slice(0, TALK_MAX_ACKS)) {
      if (!isObject(a) || typeof a.cid !== "string" || a.cid.length < 1 || a.cid.length > 64) continue;
      if (!TALK_ANSWERS.includes(a.state)) continue;
      acks.set(a.cid, { cid: a.cid, state: a.state, why: talkWhy(a.why) });
    }
    out.acks = [...acks.values()];
  }
  if (Array.isArray(raw.chat)) {
    const rows = new Map();
    for (const r of raw.chat.slice(0, TALK_MAX_CHAT)) {
      const row = readChatRow(r);
      if (row) rows.set(row.k, row);
    }
    out.chat = [...rows.values()];
  }
  if (isObject(raw.start)) out.start = readStart(raw.start);
  return out;
}

// The machine's answers for the owner's messages.
async function keepAcks(db, user, dev, acks) {
  if (acks.length === 0) return;
  await db.prepare(ACKS_SQL).bind(user, dev, JSON.stringify(acks)).run();
}

// Copy the machine's chat rows. The same row again writes nothing. Old rows
// and the overflow of a conversation go only after something was stored, so a
// quiet sync costs no extra statement.
async function keepChat(db, user, dev, rows, now) {
  if (rows.length === 0) return;
  const marks = rows.map((r) => ({ k: r.k, state: r.state, why: r.why }));
  await db.prepare(CHAT_DROP_SQL).bind(user, dev, JSON.stringify(marks)).run();
  const put = await db.prepare(CHAT_PUT_SQL).bind(user, dev, now, JSON.stringify(rows)).run();
  if (!(put.meta && put.meta.changes > 0)) return;
  await db.prepare(CHAT_OLD_SQL).bind(user, now - TALK_KEEP_MS).run();
  const names = [...new Set(rows.map((r) => r.to))];
  await db.prepare(CHAT_TRIM_SQL).bind(user, dev, JSON.stringify(names)).run();
}

// The owner's messages for this machine: time out the old ones, take the
// oldest 'sent' ones, and hand down every 'taken' one (again and again, until
// the machine answers for it). The relay never makes a message row.
async function handDown(db, user, dev, now) {
  await db.prepare(DOWN_EXPIRE_SQL).bind(user, dev, now).run();
  await db.prepare(DOWN_TAKE_SQL).bind(user, dev).run();
  const { results } = await db.prepare(DOWN_LIST_SQL).bind(user, dev).all();
  return results.map((m) => ({ cid: m.cid, to: m.pg, text: m.text, age: now - m.at }));
}

// Talk turned off on the machine: its chat copy goes, its waiting messages are
// not delivered, and its picture loses the talk flag. Each is guarded, so a
// second "off" writes nothing.
async function dropTalk(db, user, dev) {
  await db.prepare("DELETE FROM city_chat WHERE user = ? AND dev = ?").bind(user, dev).run();
  await db
    .prepare("UPDATE city_msg SET state = 'undelivered', why = 'talk-off' WHERE user = ? AND dev = ? AND state IN ('sent', 'taken', 'queued')")
    .bind(user, dev)
    .run();
  await db
    .prepare("UPDATE city_view SET counts = json_remove(counts, '$.talk') WHERE user = ? AND dev = ? AND json_extract(counts, '$.talk') IS NOT NULL")
    .bind(user, dev)
    .run();
}

// The machine's answers for the owner's orders.
async function keepOrderAcks(db, user, dev, acks, now) {
  if (acks.length === 0) return;
  await db.prepare(ORDER_ACKS_SQL).bind(user, dev, JSON.stringify(acks), now).run();
}

// The owner's orders for this machine: time out the old ones, take the oldest
// 'sent' ones, and hand down every 'taken' one (again and again, until the
// machine answers for it). The relay never makes an order row.
async function handDownOrders(db, user, dev, now) {
  await db.prepare(ORDER_EXPIRE_SQL).bind(user, dev, now).run();
  await db.prepare(ORDER_TAKE_SQL).bind(user, dev, now).run();
  const { results } = await db.prepare(ORDER_LIST_SQL).bind(user, dev).all();
  return results.map((o) => ({ oid: o.oid, terr: o.terr, force: o.force !== 0, age: now - o.at }));
}

// Starting turned off on the machine: its waiting orders failed and its picture
// loses the start flag. Each is guarded, so a second "off" writes nothing.
async function dropStart(db, user, dev, now) {
  await db.prepare(ORDER_OFF_SQL).bind(user, dev, now).run();
  await db.prepare(START_FLAG_OFF_SQL).bind(user, dev).run();
}

// The cloud page's user: CITY_USER trimmed and lower case, or "" when the
// page is off (unset or blank).
function cityUser(env) {
  return typeof env.CITY_USER === "string" ? env.CITY_USER.trim().toLowerCase() : "";
}

// The generation of the picture held for this machine, 0 = none.
async function storedGen(db, user, dev) {
  const gen = await db
    .prepare("SELECT gen FROM city_view WHERE user = ? AND dev = ?")
    .bind(user, dev)
    .first("gen");
  return gen || 0;
}

// Keep one machine's view. Every path writes at most one row: the free plan
// counts rows written. Every statement goes through the (user, dev) key or
// its `user` prefix, so none reads the whole table. Returns the gen held for
// this machine after the view, which tells the sender when to send a picture.
async function keepView(db, user, dev, view, now) {
  if (!view) return storedGen(db, user, dev);
  const counts = oneLine(view.counts);
  const events = view.events && view.events.length > 0 ? oneLine(view.events) : "";

  if (view.snap !== undefined) {
    // A new picture replaces the row in one upsert; its events are batch 1.
    const batch = events ? `{"n":1,"e":${events}}\n` : "";
    await db
      .prepare(
        "INSERT INTO city_view (user, dev, label, ts, gen, n, counts, snap, events) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) " +
          "ON CONFLICT (user, dev) DO UPDATE SET label = excluded.label, ts = excluded.ts, gen = excluded.gen, n = excluded.n, counts = excluded.counts, snap = excluded.snap, events = excluded.events"
      )
      .bind(user, dev, view.label, now, view.gen, events ? 1 : 0, counts, oneLine(view.snap), batch)
      .run();
    // Old machines go only now, so syncs without a picture write nothing extra.
    await db
      .prepare("DELETE FROM city_view WHERE user = ? AND ts <= ?")
      .bind(user, now - CITY_KEEP_MS)
      .run();
    return view.gen;
  }

  // No new picture: the row is only touched when the sender's gen is the one
  // held. Appending is one UPDATE (no read first); the new batch's number is
  // the row's n + 1, which SQL reads from the row before the same UPDATE.
  let res;
  if (events) {
    res = await db
      .prepare(
        `UPDATE city_view SET label = ?, ts = ?, counts = ?, n = n + 1, events = events || '{"n":' || (n + 1) || ',"e":' || ? || '}' || char(10) WHERE user = ? AND dev = ? AND gen = ?`
      )
      .bind(view.label, now, counts, events, user, dev, view.gen)
      .run();
  } else {
    res = await db
      .prepare("UPDATE city_view SET label = ?, ts = ?, counts = ? WHERE user = ? AND dev = ? AND gen = ?")
      .bind(view.label, now, counts, user, dev, view.gen)
      .run();
  }
  if (res.meta && res.meta.changes > 0) return view.gen;
  return storedGen(db, user, dev);
}

// The highest seq the relay has ever handed out, read without scanning the
// table: the newest row that is still there knows its own line count
// exactly. If the store is empty right now, report 0 — line seqs still
// never go back, since they come from the AUTOINCREMENT id, which SQLite
// never re-issues; a client that asks again with after=0 gets every line
// newer than that, store-was-empty or not.
async function currentSeq(db) {
  const newest = await db
    .prepare("SELECT id, n FROM relay_batch WHERE id = (SELECT MAX(id) FROM relay_batch)")
    .first();
  return newest ? newest.id * SEQ_STEP + newest.n - 1 : 0;
}

async function handleSync(request, env) {
  if (!env.TEAM_KEY) {
    return json({ ok: false, error: "relay has no TEAM_KEY set" }, 500);
  }
  if (!checkAuth(request, env.TEAM_KEY)) {
    return json({ ok: false, error: "missing or wrong key" }, 401);
  }

  const text = await request.text();
  const user = cityUser(env);
  const parsed = readSync(text, user !== "");
  if (parsed.error) return parsed.error;
  const { dev, after, lines, view } = parsed;

  // Talk is read only for a sync that is "on"; for any other, body.talk is not looked at.
  const mode = talkMode(request, env, user);
  const talk = mode === "on" ? readTalk(parsed.talk) : null;
  // The picture of a machine that talks says so, once, in its counts.
  if (talk && !talk.off && view) view.counts.talk = 1;
  // ... and so does the picture of a machine that starts agents (not one that says start is off).
  if (talk && talk.start && !talk.start.off && view) view.counts.start = 1;

  const db = env.DB;
  await db.exec(SETUP_SQL);
  if (user) await db.exec(CITY_SQL);
  if (talk) await db.exec(TALK_SQL);
  if (talk && talk.start) await db.exec(START_SQL);

  const now = Date.now();
  const cutoff = now - WINDOW_MS;
  await db.prepare("DELETE FROM relay_batch WHERE ts <= ?").bind(cutoff).run();

  let seq;
  if (lines.length > 0) {
    const ins = await db
      .prepare("INSERT INTO relay_batch (dev, ts, n, lines) VALUES (?, ?, ?, ?)")
      .bind(dev, now, lines.length, JSON.stringify(lines))
      .run();
    seq = ins.meta.last_row_id * SEQ_STEP + lines.length - 1;
  } else {
    seq = await currentSeq(db);
  }

  // Any row whose block could hold a seq above "after" has id >= this
  // floor, so the lookup can use the id index instead of reading every row.
  const afterId = Math.floor(after / SEQ_STEP);
  const { results } = await db
    .prepare("SELECT dev, id, n, lines FROM relay_batch WHERE id >= ? AND dev != ? ORDER BY id ASC")
    .bind(afterId, dev)
    .all();

  let out = [];
  for (const row of results) {
    const rowLines = JSON.parse(row.lines);
    for (let i = 0; i < rowLines.length; i++) {
      const lineSeq = row.id * SEQ_STEP + i;
      if (lineSeq > after) out.push({ seq: lineSeq, dev: row.dev, line: rowLines[i] });
    }
  }
  if (out.length > MAX_RETURN) out = out.slice(out.length - MAX_RETURN);

  const reply = { ok: true, seq, lines: out };
  if (user) {
    reply.city = true;
    reply.gen = await keepView(db, user, dev, view, now);
  }
  if (talk) {
    // In this order: the machine's answers, its chat rows, then the way down.
    if (talk.off) {
      await dropTalk(db, user, dev);
      reply.talk = { state: "off" };
    } else {
      await keepAcks(db, user, dev, talk.acks);
      await keepChat(db, user, dev, talk.chat, now);
      reply.talk = { state: "on", msgs: await handDown(db, user, dev, now) };
      // Then the orders, only when the talk has "start": its answers, then the way down.
      if (talk.start && talk.start.off) {
        await dropStart(db, user, dev, now);
        reply.talk.start = { state: "off" };
      } else if (talk.start) {
        await keepOrderAcks(db, user, dev, talk.start.acks, now);
        reply.talk.start = { state: "on", orders: await handDownOrders(db, user, dev, now) };
      }
    }
  } else if (mode !== "none") {
    reply.talk = { state: mode };
  }
  return json(reply, 200);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/" && request.method === "GET") {
      return json({ ok: true, relay: "agent-city", v: 1 }, 200);
    }

    if (url.pathname === "/v1/sync") {
      if (request.method !== "POST") {
        return json({ ok: false, error: "use POST" }, 405);
      }
      return handleSync(request, env);
    }

    return json({ ok: false, error: "not found" }, 404);
  },
};
