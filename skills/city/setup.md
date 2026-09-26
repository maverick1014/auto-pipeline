# City relay setup

Hand steps for a team owner. Follow them once, in order, on your own free
Cloudflare account. You do not need any Cloudflare experience: every step
says what you should see when it works. Nobody else on the team needs to
do this — once you finish, you hand two things to each member (the relay
address and the team key), and they join with them.

The relay runs on Cloudflare's free plan: 100,000 Worker requests a day,
which is enough for many joined machines (each syncs about every 5
seconds while its city runs).

## 1. Make a Cloudflare account
1. Open a browser and go to https://dash.cloudflare.com/sign-up .
2. Enter your email address and a password, then submit the form.
   You should see: a message asking you to check your email.
3. Open the email from Cloudflare and click the confirm link in it.
   You should see: your browser opens the Cloudflare dashboard.
4. If it asks you to pick a plan, pick the Free plan.
   You should see: the dashboard home page, with "Workers & Pages" in the
   left menu.

## 2. Make the relay
1. In the left menu, click "Workers & Pages".
2. Click "Create", then choose "Worker" (a plain Worker, not a template).
3. Give it any name and click "Deploy".
   You should see: a page saying the Worker is live, with an "Edit code"
   button.
4. Click "Edit code". This opens the Worker's code editor.
5. On your own Mac, in your own terminal, copy the relay code
   (`agent-city-relay.js`) to the clipboard:
   ```
   cat "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city-relay.js" | pbcopy
   ```
6. In the Cloudflare editor, select all of the sample code, delete it, and
   paste. This is the whole relay, `agent-city-relay.js`.
7. Click "Deploy" (or "Save and deploy").
   You should see: the editor says the deploy succeeded.
8. In the left menu, click "Storage & Databases", then "D1".
9. Click "Create database", give it any name, and create it.
   You should see: a new, empty database page.
10. Go back to your Worker's "Settings", then "Bindings", then "Add".
11. Choose "D1 database", pick the database you just made, and set the
    variable name to exactly `DB`.
    You should see: `DB` listed as a binding for the Worker.
12. Save. You do not write any SQL by hand: the Worker makes its own
    table itself, the first time it runs.

## 3. Set the team key
1. On your own Mac, in your own terminal, make a random key:
   ```
   openssl rand -hex 24
   ```
   You should see: a long string of letters and numbers printed in your
   terminal. Keep this terminal open; you will copy the string from it.
2. In your Worker, open "Settings", then "Variables and Secrets", then
   "Add".
3. Set the type to "Secret", the name to exactly `TEAM_KEY`, and the
   value to the string from step 1.
4. Click "Deploy" (or "Save").
   You should see: `TEAM_KEY` listed under Secrets, its value hidden.

Never type the key into a chat with Claude or any agent. It is a secret:
keep it only in your terminal, in Cloudflare, and with your members.

## 4. Find the relay address
1. Open your Worker's overview page.
   You should see: an address of the shape
   `https://<worker name>.<account subdomain>.workers.dev`.
2. Open that address in a browser.
   You should see: `{"ok":true,"relay":"agent-city","v":1}`.
3. Check it from a terminal as well, because machines join without a
   browser sign-in. On your Mac, run (put your own address in):
   ```
   curl -s https://<worker name>.<account subdomain>.workers.dev/
   ```
   You should see: the same `{"ok":true,"relay":"agent-city","v":1}`.
4. Only if step 3 shows anything else (a `302 Found` page, a sign-in
   page, or nothing at all):
   Cloudflare Access stands in front of the relay and would lock out
   every machine that joins. Open the Worker's "Domains" tab (on older
   dashboards: "Settings", then "Domains & Routes"). Next to `workers.dev`,
   click "Disable Cloudflare Access", then run step 3 again.
   You should see: step 3 now shows the relay's answer.

This address is not secret; the team key is what protects the relay.

## 5. Hand the address and key to members
1. Send the relay address to each member any way you like (chat, email,
   a doc).
2. Send the team key to each member over a private channel you trust (in
   person, a password manager, a phone call). Never paste it into a chat
   with an agent.
   You should see: each member has both the address and the key.

## 6. Join a local repo
1. Ask each member to open their own terminal, inside the repo they want
   to join (the main repo or one of its worktrees).
2. Run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" join
   ```
3. It asks for the relay address, then the team key (typed hidden,
   nothing shown on screen).
   You should see: after a moment, `JOINED: <repo id> -> <host>`.

This saves the address and key to `<repo>/.secrets/agent-city-relay`, on
that machine only. It refuses when the repo has no `origin` remote, or
when `.secrets/` is not git-ignored.

## 7. Join a cloud environment
Cloud sessions (Claude Code on the web / in the Claude app) have no city
page; they only send, and show up in the city on your Mac.
1. Make sure each repo you work on in the cloud carries the current cloud
   pack (it ships the city hook and the sender). On your Mac, inside the
   repo, run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-cloud-pack.sh" . --update
   ```
   then commit and push what it changed. You should see: `.claude/auto-pipeline/VERSION` shows the plugin's
   version, and `.claude/settings.json` has hooks that run
   `agent-city-hook.sh`.
2. Open a cloud session, click the cloud environment menu in the session's
   title bar, then "Edit".
3. Add an environment variable named `AGENT_CITY_RELAY`. Its value is the
   relay address, one space, then the team key: `<relay address>
   <team key>`. Type it there yourself; never in a chat.
4. Under "Network access", add the relay host to the allowed domains:
   `<worker name>.<account subdomain>.workers.dev`.
   You should see: the host listed under the allowed domains, and the
   variable listed.
5. Start a new cloud session (a running one does not see the change).
   You should see: at its start, the line
   `CITY: sending to the team relay <worker name>.<account subdomain>.workers.dev`.

## 8. Check it works
1. On a second machine, or in a cloud session, join the same repo (step
   6, or the cloud secret from step 7).
2. In a terminal, inside the repo, run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" status
   ```
   You should see: a line `TEAM: joined <host>`.
3. Open the city page on one machine while agents run on the other.
   You should see: the other machine's people show up in the city. If
   the relay is down or offline, the page shows 联城断开 instead.

## 9. Change the key
1. In Cloudflare, open the Worker's "Settings", then "Variables and
   Secrets".
2. Edit `TEAM_KEY` and set a new value (make one the same way as step 3:
   `openssl rand -hex 24`).
3. Deploy.
   You should see: `TEAM_KEY` still listed, its value still hidden.
4. Hand the new key to every member the same way as step 5.
5. Every member runs `join` again, with the address and the new key.
   You should see: `JOINED: <repo id> -> <host>` on every member's
   machine again.

## 10. Remove the relay
1. On every member's machine, in every joined repo, run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" leave
   ```
   You should see: `LEFT: ...` on each machine.
2. In Cloudflare, open the Worker and delete it.
3. Open D1 and delete the database you made in section 2.
   You should see: neither the Worker nor the database listed any more.
