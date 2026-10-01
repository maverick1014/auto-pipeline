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

const WINDOW_MS = 300_000; // how long a line is handed out for
const MAX_LINES = 200; // lines allowed in one sync
const MAX_BODY_BYTES = 256 * 1024; // body size cap
const MAX_RETURN = 500; // lines handed back in one reply, newest kept
const MAX_EVENTS = 500; // page messages allowed in one view
const CITY_KEEP_MS = 24 * 3600 * 1000; // a machine not heard from this long is dropped

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

// Turn the raw request body text into a validated {dev, after, lines, view},
// or return the error Response to send straight back. The view is only read
// when the cloud page is on; otherwise it is ignored, bad or not.
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
  return { dev, after, lines, view };
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

  const db = env.DB;
  await db.exec(SETUP_SQL);
  if (user) await db.exec(CITY_SQL);

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
