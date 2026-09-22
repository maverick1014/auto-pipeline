#!/usr/bin/env bash
# agent-resources.sh — RAM and CPU readers, sourced by other scripts.
#
#   . ./agent-resources.sh
#   ram_used              -> percent used, or -1 when it cannot tell
#   cpu_used               -> percent used, or -1 when it cannot tell
#   resources_read         -> reads once into RAM_USED and CPU_USED (skips if already set)
#   resources_line <cap>   -> "RESOURCES: RAM <n>% CPU <n>% (cap <n>%) -> OK" or "-> OVER CAP"
#   resources_ok <cap>     -> exit 0 when both readings are under the cap
#
# AGENT_FAKE_RAM and AGENT_FAKE_CPU, when set, replace the real readings.
# Meant to be sourced, not executed directly.

ram_used() {
  if [ -n "${AGENT_FAKE_RAM:-}" ]; then echo "$AGENT_FAKE_RAM"; return; fi
  if [ "$(uname)" = Darwin ]; then
    f=$(memory_pressure 2>/dev/null | awk -F': ' '/free percentage/{gsub("%","",$2);print $2}')
    [ -n "$f" ] && echo $((100 - f)) || echo -1
  else
    awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{if(t)printf "%d",(t-a)*100/t; else print -1}' /proc/meminfo
  fi
}
cpu_used() {
  if [ -n "${AGENT_FAKE_CPU:-}" ]; then echo "$AGENT_FAKE_CPU"; return; fi
  if [ "$(uname)" = Darwin ]; then
    i=$(top -l 2 -n 0 -s 1 2>/dev/null | awk '/CPU usage/{idle=$7}END{gsub("%","",idle);print idle}')
    [ -n "$i" ] && printf '%d\n' "${i%.*}" | awk '{print 100-$1}' || echo -1
  else
    read -r _ a b c d _ < /proc/stat; sleep 1; read -r _ a2 b2 c2 d2 _ < /proc/stat
    t=$(( (a2+b2+c2+d2)-(a+b+c+d) )); id=$(( d2-d ))
    [ "$t" -gt 0 ] && echo $(( (t-id)*100/t )) || echo -1
  fi
}

resources_read() {
  [ -n "${RAM_USED:-}" ] || RAM_USED=$(ram_used)
  [ -n "${CPU_USED:-}" ] || CPU_USED=$(cpu_used)
}

resources_line() {
  cap=$1
  resources_read
  r=$RAM_USED; c=$CPU_USED
  if [ "$r" -ge "$cap" ] || [ "$c" -ge "$cap" ]; then
    echo "RESOURCES: RAM ${r}% CPU ${c}% (cap ${cap}%) -> OVER CAP"
  else
    echo "RESOURCES: RAM ${r}% CPU ${c}% (cap ${cap}%) -> OK"
  fi
}

resources_ok() {
  cap=$1
  resources_read
  [ "$RAM_USED" -lt "$cap" ] && [ "$CPU_USED" -lt "$cap" ]
}
