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
6. Start a new cloud session, opened on ONE repo that carries the cloud pack. A session opened on several repos starts above them and runs none of their hooks, so it sends nothing (step 7 fixes that).
You should see: at the session's start, the line `CITY: sending to the team relay <worker name>.<account subdomain>.workers.dev`.
7. For sessions opened on several repos: in the same "Edit" screen, paste this into the Setup script (keep step 1 too):
   ```
   git clone --depth 1 https://github.com/maverick1014/auto-pipeline /tmp/ap-city && bash /tmp/ap-city/bin/agent-city.sh cloud-hooks
   ```
   Then start a new cloud session on several repos.
   You should see: `CITY: user hooks written to .../settings.json` (or `CITY: user hooks already there`), and the session shows up in the city like step 6.

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

## 11. Turn the cloud page on
Optional. Do this only after sections 1 to 8 work. The cloud page is your city on Cloudflare, behind a login, to look at from a phone or any computer. It is view only until you turn talking on (section 16). The local city on your Mac stays as it is, and works with Cloudflare down.
1. On your Mac, in a terminal, copy the NEW relay code to the clipboard (the same command as section 2, step 5):
   ```
   cat "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city-relay.js" | pbcopy
   ```
2. In Cloudflare, click "Workers & Pages", then your relay Worker (the one from section 2), then "Edit code".
3. Click inside the code, press Cmd+A, then Delete, then Cmd+V. Do NOT delete the file `worker.js` itself (see section 2, step 6).
4. Click "Deploy" (or "Save and deploy").
5. Open the Worker's "Settings", then "Variables and Secrets", then "Add".
6. Set the type to "Text" (not "Secret"), the name to exactly `CITY_USER`, the value to your e-mail: the one you will log in with in section 13.
7. Click "Deploy" (or "Save").
You should see: `CITY_USER` listed under the Worker's variables, with your e-mail as its value. The team key and the machines that joined need no change.

## 12. Deploy the cloud page
1. Find the D1 database id: in Cloudflare, click "Storage & Databases" in the left menu, then "D1", then the database you made in section 2. Copy its "Database ID" (shape: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`; not a secret). The page reads this same database.
2. On your Mac, in a terminal, run `node --version`. If it prints a version number, go on. If it says `command not found`, install Node.js from https://nodejs.org (the LTS version), then open a new terminal.
3. Log in to Cloudflare from the terminal:
   ```
   npx wrangler login
   ```
   A browser opens; click "Allow". If `npx` asks "Ok to proceed?", type `y`. Type this yourself, in your own terminal: never in a chat with Claude or any agent, and never let an agent run it or the deploy for you.
4. Deploy the page:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" cloud-deploy
   ```
5. Paste the database id from step 1 when asked, press Enter. It remembers the id: the next time, press Enter to keep it. If the deploy says you are not logged in, do step 3 again, then run step 4 again.
You should see: `wrangler` prints the page's address, shape `https://agent-city-page.<account subdomain>.workers.dev`. Open it: it answers "login required", and that is right. The page stays closed until the login is set up (section 13). After a plugin update, run step 4 again to put the new page code on Cloudflare.

## 13. Set up the login
1. In Cloudflare, click "Workers & Pages", then the new Worker `agent-city-page`.
2. Open "Settings", then "Domains & Routes" (older dashboards: the "Domains" tab).
3. Next to `workers.dev`, click "Enable Cloudflare Access", then "Manage Cloudflare Access". Cloudflare may ask you to pick the free Zero Trust plan, and may ask for a payment card for it: pick the free plan, it costs nothing.
4. In the Access policy, allow only your own e-mail: the same one as `CITY_USER` in section 11. Nobody else may be listed.
5. For the login method, use the one-time code sent by e-mail ("One-time PIN", on by default).
6. Find your team name: open Zero Trust, then "Settings". The team domain looks like `<team name>.cloudflareaccess.com`; copy the part before `.cloudflareaccess.com`.
7. Find the audience tag: in Zero Trust, open "Access", then "Applications", then the application for `agent-city-page`. Copy its "Application Audience (AUD) Tag".
8. Back on the Worker `agent-city-page`, open "Settings", then "Variables and Secrets", then "Add". Set the type to "Text", the name to exactly `ACCESS_TEAM`, the value to the team name from step 6. Add another, type "Text", the name exactly `ACCESS_AUD`, the value to the tag from step 7.
9. Click "Deploy" (or "Save"). Type these two values only here in the dashboard; the deploy never writes them to a file.
10. Do NOT enable Cloudflare Access on the relay Worker: machines join without a browser (section 4), and a login in front of the relay would stop them.
You should see: opening the page's address shows Cloudflare's login page asking for your e-mail, then a 6-digit code sent to that e-mail, then the city. If the page still says "login required" after you logged in, `ACCESS_TEAM` or `ACCESS_AUD` is wrong or missing: check both names and values in step 8.

## 14. Check the cloud page
1. Nothing has to be typed on the machines. On a machine that joined (section 6), the city starts by itself when a Claude session starts, so there is no need to type `agent-city start`.
2. Start (or go on with) a Claude session in a repo you joined (section 6). Wait about a minute.
3. In a terminal, inside that repo, run (the same command as section 8, step 2):
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" status
   ```
4. Open the page's address on your phone and log in with the e-mail code (section 13).
You should see: `CLOUD: on <relay host>` from step 3 (`CLOUD: off` means the relay has no `CITY_USER` (section 11), or the session has not started yet: start a new one), and on the phone a machine row on top and the city under it, view only: 只能看, no chat box, no buttons. The notices say what is missing: 还没有机器 = no machine has sent a picture yet (wait a minute more; check step 3); 这台机器现在没有会话 = that machine has no session right now; 没有机器在线 = no machine is online, with how long ago the last picture came (the picture stays); a notice that the login is lost = open the address again and log in again. Only repos that joined (section 6) show up; a repo that did not join never leaves its machine.

## 15. Turn the cloud page off
1. In Cloudflare, open the relay Worker, then "Settings", then "Variables and Secrets". Delete `CITY_USER`, then "Deploy". The machines stop sending pictures; after the next Claude session on a machine, `status` says `CLOUD: off` there.
2. Open "Workers & Pages", then the Worker `agent-city-page`, then "Settings"; at the bottom, delete the Worker. If Zero Trust still lists an Access application for it ("Access", then "Applications"), delete that too.
You should see: `CITY_USER` no longer listed on the relay, the page's address no longer opens, and `CLOUD: off` from `status` after the next session. The relay and the local city go on as before.

## 16. Turn talking on
Optional. Do this only after sections 1 to 15 work. With talking on, you can type to your agents from the cloud page, and the reply shows in the same window. Read this first, in plain words: whoever can log in as you on the page can type to your agents on the machines with talking on. So keep the login short (step 1) and keep your e-mail account safe: use a strong password and two-step login on the e-mail account, because the login code goes there. A message is only text for a session's chat. Approving a permission request stays on the machine: you cannot do it from the page. Talking is off by default: it stays off for a machine until you do step 7 on it.
1. Set how long a login lasts. In Cloudflare, open Zero Trust, then "Access", then "Applications", then the application for `agent-city-page`, then "Edit". Find the setting "Session Duration" and pick a short one (for example 24 hours or less). Save.
2. On your Mac, in a terminal, copy the NEW relay code to the clipboard (the same command as section 2, step 5):
   ```
   cat "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city-relay.js" | pbcopy
   ```
3. In Cloudflare, click "Workers & Pages", then your relay Worker (the one from section 2), then "Edit code". Click inside the code, press Cmd+A, then Delete, then Cmd+V. Do NOT delete the file `worker.js` itself (see section 2, step 6). Click "Deploy" (or "Save and deploy").
4. Make the talk key. This is a second key, not the team key. In a terminal, run:
   ```
   openssl rand -hex 24
   ```
5. Keep this terminal open: you will copy the string from it. On the relay Worker, open "Settings", then "Variables and Secrets", then "Add". Set the type to "Secret", the name to exactly `TALK_KEY`, the value to the string from step 4. Click "Deploy" (or "Save"). Never type the talk key into a chat with Claude or any agent: keep it only in your terminal and in Cloudflare.
6. Deploy the NEW page code (the same command as section 12, step 4):
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" cloud-deploy
   ```
   Press Enter to keep the database id it remembers. If it says you are not logged in, do section 12, step 3 again, then run this step again.
7. Do this on each machine that should take messages. In a terminal, inside a repo that joined (section 6), run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" cloud-talk on
   ```
   It asks "Talk key (hidden):". Paste the talk key from step 4 (nothing is shown), press Enter. Type this yourself, in your own terminal: the command refuses when an agent runs it, and you never give the key to an agent.
8. Check it. On that machine, in a terminal, inside the repo, run the status command (the same as section 8, step 2):
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" status
   ```
9. Open the cloud page and log in. Wait about a minute. Tap that machine, then tap a person.
What is stored: your messages and the conversations of machines with talking on go to your own Cloudflare database, for 7 days and at most 200 rows per conversation. The full record stays on the machine. A machine with talking off sends no conversation at all.
To start new agents from the page as well (a button on the page opens a new agent on that machine), go on with section 18 (starting agents from the page) after this section works.
You should see: `CLOUD TALK: on <relay host>` from step 8. On the page, that machine shows 可对话, and a person's window has the message box. A message typed there shows 在路上 (on its way), then 已送达 (delivered), then the reply of the session. A machine that did not do step 7 still shows 只能看.

## 17. Turn talking off
There are three ways to stop it. Use the one you need, or all of them.
1. One machine. On that machine, in a terminal (from any folder), run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" cloud-talk off
   ```
   Run inside the repo that joined (section 6), it also deletes the conversations of that machine on Cloudflare at once. Run from another folder, it still turns talking off on that machine, and its conversations on Cloudflare leave by themselves within 7 days. The other machines go on as before.
2. All machines at once. In Cloudflare, open the relay Worker, then "Settings", then "Variables and Secrets". Delete `TALK_KEY`, then "Deploy". With no `TALK_KEY`, talking is off for every machine.
3. End the login. On the page, click the 退出 link. To end the Access session everywhere (for example if someone else may have your login): in Cloudflare, open Zero Trust, then "My Team", then "Users", click your user, then "Revoke". Every login on every device must log in again with an e-mail code.
You should see: `CLOUD TALK: off` from step 1 (the same status command as section 16, step 8 shows it too), and on the page that machine shows 只能看, with no message box. After step 2, no machine takes a message. The cloud page itself, the relay and the local city go on as before.

## 18. Turn starting agents on
Optional. Do this only after section 16 works: talking must be on first, on each machine that should take orders. With starting on, you can open a new agent from the cloud page, in a repo that joined (section 6) on a machine with starting on, and then type to it. Read this first, in plain words: whoever can log in as you on the page can open a Manager or a Helper (the two kinds of agent you talk to yourself) in a joined repo of a machine with starting on, and then type to it (talking is on there). So keep the login short (section 16, step 1) and keep your e-mail account safe. The command is fixed: nobody can choose the role, the model, a flag or a folder. A task manager is never made this way. At most 10 an hour can be started. Every order, and what became of it, is written in decisions.jsonl on that machine. A machine with starting on keeps its small city program running also when no session is open, so the first agent of the day can be started from the phone. After a restart of the computer it comes back with the next Claude session there, when you run `agent-city start`, or by itself at login when you turn that on (section 20). Starting is off by default: it stays off for a machine until you do step 5 on it.
1. On your Mac, in a terminal, copy the NEW relay code to the clipboard (the same command as section 2, step 5):
   ```
   cat "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city-relay.js" | pbcopy
   ```
2. In Cloudflare, click "Workers & Pages", then your relay Worker (the one from section 2), then "Edit code". Click inside the code, press Cmd+A, then Delete, then Cmd+V. Do NOT delete the file `worker.js` itself (see section 2, step 6). Click "Deploy" (or "Save and deploy").
3. Deploy the NEW page code (the same command as section 12, step 4):
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" cloud-deploy
   ```
   Press Enter to keep the database id it remembers. If it says you are not logged in, do section 12, step 3 again, then run this step again.
4. Check that talking is on for each machine that should take orders: run the status command (the same as section 8, step 2) there and look for `CLOUD TALK: on <relay host>`. If it says `CLOUD TALK: off`, do section 16, step 7 first.
5. Do this on each machine that should take orders. In a terminal, inside a repo that joined (section 6), run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" cloud-start on
   ```
   It asks "Talk key (hidden):". Type the talk key from section 16 again (nothing is shown), press Enter. There is no new key: it is the same talk key. Type this yourself, in your own terminal: the command refuses when an agent runs it, and never type the talk key into a chat with Claude or any agent.
6. Check it. On that machine, in a terminal, inside the repo, run the status command (the same as section 8, step 2):
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" status
   ```
7. Open the cloud page and log in. Wait about a minute. Tap that machine.
You should see: `CLOUD START: on <relay host>` from step 6. On the page, that machine's row shows 可开 agent, and each repo that lives on that machine has the button 加 agent. Click it: it shows 在路上 (on its way), then that computer opens the session, then the new person appears in the city and you can type to it. A machine that did not do step 5 has no such button.

## 19. Turn starting agents off
There are three ways to stop it. Use the one you need, or all of them.
1. One machine. On that machine, in a terminal (from any folder), run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" cloud-start off
   ```
   Run inside the repo that joined (section 6), it also tells Cloudflare, so an order that is still waiting is never opened. Talking stays on. Turning talking off (`cloud-talk off`, section 17, step 1) turns starting off on that machine too. The other machines go on as before.
2. All machines at once. In Cloudflare, open the relay Worker, then "Settings", then "Variables and Secrets". Delete `TALK_KEY`, then "Deploy". With no `TALK_KEY`, no machine takes an order, and talking is off for every machine too.
3. End the login. On the page, click the 退出 link. To end the Access session everywhere (for example if someone else may have your login): the same as section 17, step 3 (Zero Trust, "My Team", "Users", your user, "Revoke").
You should see: `CLOUD START: off` from step 1 (the status command of section 18, step 6 shows it too), and on the page no 加 agent button for that machine, with a note at the foot of the list saying how to turn it on. After step 2, no machine takes an order. The cloud page, the relay and the local city go on as before.

## 20. Start the city when you log in
Optional. It lets the small city program start by itself when you log in, so the cloud page sees this computer after a restart. Read this first, in plain words: the cloud page shows a machine only while its small city program runs. That program starts when a Claude session starts. After the computer restarts, nothing runs until you open a session, so the cloud page says the machine is off. This step fixes that. It works only on a Mac for now. It only does something while the cloud page is on for this machine (section 11 and section 14). It is off by default: it stays off until you do step 1. After a plugin update there is nothing to do again.
1. Turn it on. On your Mac, in a terminal (from any folder), run:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" login-start on
   ```
   Type this yourself, in your own terminal: the command refuses when an agent runs it.
2. Check it. Run the status command (the same as section 8, step 2):
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" status
   ```
3. Check it for real. Restart the computer (or log out and log in). Do not open a Claude session. Wait about a minute. Then open the cloud page on your phone and log in (section 13).
4. To turn it off, run this on the same Mac, in a terminal, from any folder:
   ```
   bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" login-start off
   ```
   A small city program that runs now stays up until it stops by itself, or until you run `agent-city stop`.
About the idle rule: with starting agents off (section 18 not done), the small city program stops by itself after 30 minutes with no session and no browser. It comes back with the next session or the next login. With section 18 done, it stays up.
You should see: `LOGIN START: on` after step 1, and as the last line of step 2. After step 3, this machine is on the cloud page. After step 4, `LOGIN START: off`.

Cloudflare's free plan allows 100,000 Worker requests and 100,000 D1 rows written a day. A heavy day (3 machines, 6 busy hours each, the page open 8 hours) uses about 44,500 requests and about 73,900 written rows. This day includes talking: 600 session turns and 100 messages from the page. It also includes starting: 20 agents started from the page, and each machine kept up the other 12 hours with nobody there. About 52,000 of those rows are the relay's lines as before, talking adds about 6,000, and starting adds about 8,700 requests and about 2,300 rows.
