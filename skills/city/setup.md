# City relay setup

Set up your own relay on your own free Cloudflare account. Do this once; then hand the address and team key to each member (they join with them).

## 1. Make a Cloudflare account
1. Go to https://dash.cloudflare.com/sign-up .
2. Enter your email and a password, submit.
3. Open the confirmation email, click the link in it.
4. If asked to pick a plan, pick Free.
You should see: the dashboard home page, with "Workers & Pages" in the left menu.

## 2. Make the relay
1. Click "Workers & Pages" in the left menu.
2. Click "Create", then choose "Worker" (a plain Worker, not a template).
3. Give it any name, click "Deploy".
4. Click "Edit code" to open the code editor.
5. On your Mac, in a terminal, copy the relay code to the clipboard:
   ```
   cat "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city-relay.js" | pbcopy
   ```
6. In the Cloudflare editor, click inside the code, press Cmd+A, then Delete, then Cmd+V.
   Do NOT delete the file `worker.js` itself — deleting it blocks saving and the Worker stays "Hello world". `agent-city-relay.js` is only the name of the file you just copied on your Mac; the file in the editor stays named `worker.js`.
7. Click "Deploy" (or "Save and deploy").
8. In the left menu, click "Storage & Databases", then "D1".
9. Click "Create database", give it any name, create it.
10. Go back to your Worker's "Settings", then "Bindings", then "Add".
11. Choose "D1 database", pick the database you just made, set the variable name to exactly `DB`.
12. Save.
You should see: the editor says the deploy succeeded, and `DB` listed as a binding for the Worker. If `join` (section 6) later says `RELAY: cannot reach ...` but the address opens fine in a browser, the binding name is wrong or missing — it must be exactly `DB`.

## 3. Set the team key
1. On your Mac, in a terminal, run:
   ```
   openssl rand -hex 24
   ```
2. Keep this terminal open — you will copy the string from it.
3. In your Worker, open "Settings", then "Variables and Secrets", then "Add".
4. Set the type to "Secret", the name to exactly `TEAM_KEY`, the value to the string from step 1.
5. Click "Deploy" (or "Save").
You should see: `TEAM_KEY` listed under Secrets, its value hidden. Never type the key into a chat with Claude or any agent — keep it only in your terminal, in Cloudflare, and with your members.

## 4. Find the relay address
1. Open your Worker's overview page.
2. Copy the address (shape: `https://<worker name>.<account subdomain>.workers.dev`).
3. Open that address in a browser.
4. Check it from a terminal too, because machines join without a browser sign-in:
   ```
   curl -s https://<worker name>.<account subdomain>.workers.dev/
   ```
5. If step 4 shows anything other than `{"ok":true,"relay":"agent-city","v":1}` (a `302 Found`, a sign-in page, or nothing): open the Worker's "Domains" tab (older dashboards: "Settings", then "Domains & Routes"), and next to `workers.dev` click "Disable Cloudflare Access". Run step 4 again.
You should see: both the browser and `curl` show `{"ok":true,"relay":"agent-city","v":1}`. The address itself is not secret.

## 5. Hand the address and key to members
1. Send the relay address any way you like (chat, email, a doc) — it is not secret.
2. Send the team key over a private channel you trust (in person, a password manager, a phone call) — never in a chat with an agent.
You should see: each member has both the address and the key.

## 6. Join a local repo
1. Open a terminal inside the repo you want to join (the main repo or a worktree).
2. Run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" join
   ```
3. Enter the relay address, then the team key (typed hidden, nothing shown).
You should see: `JOINED: <repo id> -> <host>`. This saves the address and key to `<repo>/.secrets/agent-city-relay`, on that machine only.

## 7. Join a cloud environment
1. On your Mac, inside the repo, run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-cloud-pack.sh" . --update
   ```
2. Commit and push what it changed.
3. Open a cloud session, click the cloud environment menu in the session's title bar, then "Edit".
4. Add an environment variable named `AGENT_CITY_RELAY`, value: `<relay address> <team key>` (one space between them, typed there yourself, never in a chat).
5. Under "Network access", add the relay host to the allowed domains: `<worker name>.<account subdomain>.workers.dev`.
6. Start a new cloud session, opened on ONE repo that carries the cloud pack. A session opened on several repos starts above them and runs none of their hooks, so it sends nothing.
You should see: at the session's start, the line `CITY: sending to the team relay <worker name>.<account subdomain>.workers.dev`.

## 8. Check it works
1. On a second machine, or in a cloud session, join the same repo (section 6, or the cloud secret from section 7).
2. In a terminal, inside the repo, run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" status
   ```
3. Open the city page on one machine while agents run on the other.
You should see: `TEAM: joined <host>` from step 2, and the other machine's people showing up in the city page. If the relay is down or offline, the page shows 联城断开 instead.

## 9. Change the key
1. In Cloudflare, open the Worker's "Settings", then "Variables and Secrets".
2. Edit `TEAM_KEY`, set a new value (same way as section 3: `openssl rand -hex 24`).
3. Deploy.
4. Hand the new key to every member the same way as section 5.
5. Every member runs `join` again, with the address and the new key.
You should see: `JOINED: <repo id> -> <host>` on every member's machine again.

## 10. Remove the relay
1. On every member's machine, in every joined repo, run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" leave
   ```
2. In Cloudflare, open the Worker and delete it.
3. Open D1 and delete the database you made in section 2.
You should see: `LEFT: ...` on each machine, and neither the Worker nor the database listed any more.

The relay runs on Cloudflare's free plan: 100,000 Worker requests a day, enough for many joined machines.
