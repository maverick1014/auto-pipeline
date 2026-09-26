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

const WINDOW_MS = 300_000; // how long a line is handed out for
const MAX_LINES = 200; // lines allowed in one sync
const MAX_BODY_BYTES = 256 * 1024; // body size cap
const MAX_RETURN = 500; // lines handed back in one reply, newest kept

// Each stored row (one batch) claims a block of SEQ_STEP seq numbers, the
// row's id times SEQ_STEP, plus the line's place in the batch. SEQ_STEP
// must stay bigger than MAX_LINES so two batches never share a number, and
// a later batch's block always sits above every earlier one's.
const SEQ_STEP = 1000;

// D1 runs exec() one line at a time, so every statement here is one line.
const SETUP_SQL = `CREATE TABLE IF NOT EXISTS relay_batch (id INTEGER PRIMARY KEY AUTOINCREMENT, dev TEXT NOT NULL, ts INTEGER NOT NULL, n INTEGER NOT NULL, lines TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS relay_batch_ts ON relay_batch (ts);`;

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

// Turn the raw request body text into a validated {dev, after, lines}, or
// return the error Response to send straight back.
function readSync(text) {
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
  return { dev, after, lines };
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
  const parsed = readSync(text);
  if (parsed.error) return parsed.error;
  const { dev, after, lines } = parsed;

  const db = env.DB;
  await db.exec(SETUP_SQL);

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

  return json({ ok: true, seq, lines: out }, 200);
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
