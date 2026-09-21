---
name: settings
description: Show and change agent.conf values from the chat. No server, no browser. Use when the human types /settings or asks to change a limit, model, effort or permission mode.
---
# /settings — edit agent.conf in the chat (PRINCIPLES.md S1)

1. Show the file as a table, one row per key:
   ```
   python3 -c "import agent_conf; [print(k, '=', v) for k, v in agent_conf.load('agent.conf').items()]"
   ```
2. Ask with `AskUserQuestion`, one question: which key to change. Options = the keys.
3. Ask the new value. For a limit key offer 3 sensible numbers. For a role key offer model:effort pairs. For permission_mode offer default, acceptEdits, auto, plan.
4. Validate and write with the same rules as the settings page:
   ```
   python3 -c "import agent_conf; c=agent_conf.load('agent.conf'); c['<key>']='<value>'; agent_conf.validate(c); agent_conf.save(c, 'agent.conf'); print('saved')"
   ```
   Validation error → show it, ask again. Never write an invalid value.
5. Show the table again. Say: takes effect at the next agent start.
