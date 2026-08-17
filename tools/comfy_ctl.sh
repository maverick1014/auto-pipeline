#!/bin/bash
# ComfyUI 启停控制 —— 必须用这个,不要直接 pkill + 重启
#
# 踩过的坑: pkill 之后进程要几秒才真正退出并释放端口 8188。
# 立刻启动新实例会 "Port already in use" 静默失败,而旧实例继续服务 ——
# 表面看起来正常,实际跑的是旧配置,还会有两个进程抢 8 GB 内存。

COMFY_DIR="$HOME/ComfyUI"
PORT=8188
LOG=/tmp/comfyui.log

port_busy() { lsof -ti:$PORT >/dev/null 2>&1; }

# 用端口找进程,不要用 pkill -f "ComfyUI/main.py" ——
# start.sh 是 cd 之后跑 ./venv/bin/python main.py,命令行里没有那个路径串,
# 之前一直匹配不上,每次都靠 lsof 强杀兜底(日志里的"优雅退出超时")。
comfy_pid() { lsof -ti:$PORT 2>/dev/null | head -1; }

stop() {
  pid=$(comfy_pid)
  [ -n "$pid" ] && kill "$pid" 2>/dev/null
  for _ in $(seq 30); do
    port_busy || { echo "已停止"; return 0; }
    sleep 1
  done
  echo "优雅退出超时,强制终止"
  lsof -ti:$PORT 2>/dev/null | xargs -r kill -9 2>/dev/null
  sleep 2
  port_busy && { echo "❌ 端口仍被占用"; return 1; }
  echo "已强制停止"
}

start() {
  if port_busy; then
    echo "❌ 端口 $PORT 已被占用 —— 先跑 stop"
    return 1
  fi
  # 额外参数透传给 start.sh。低内存场景用:
  #   comfy_ctl.sh start --lowvram --disable-smart-memory
  # 实测 --lowvram 对热启动速度几乎无影响(75.9s vs 74.2s),
  # 只有首次加载慢很多(319s vs 93s) —— 内存吃紧时这个代价值得。
  nohup "$COMFY_DIR/start.sh" "$@" > "$LOG" 2>&1 &
  for _ in $(seq 120); do
    curl -s -m 2 "http://127.0.0.1:$PORT/system_stats" >/dev/null 2>&1 && {
      echo "✅ 就绪"
      curl -s -m 5 "http://127.0.0.1:$PORT/system_stats" \
        | python3 -c "import sys,json;d=json.load(sys.stdin)['system'];print(f\"   RAM free {d['ram_free']/1e9:.2f} GB / {d['ram_total']/1e9:.1f} GB\")" 2>/dev/null
      return 0
    }
    sleep 2
  done
  echo "❌ 启动超时,日志:"; tail -15 "$LOG"
  return 1
}

case "${1:-}" in
  start)   shift; start "$@" ;;
  stop)    stop ;;
  restart) shift; stop && start "$@" ;;
  lowmem)  stop >/dev/null 2>&1; start --lowvram --disable-smart-memory ;;
  status)
    if port_busy; then echo "运行中 (pid $(lsof -ti:$PORT | tr '\n' ' '))"
    else echo "未运行"; fi ;;
  log)     tail -"${2:-40}" "$LOG" ;;
  mem)
    pid=$(comfy_pid)
    [ -n "$pid" ] && ps -o rss= -p "$pid" | awk '{printf "ComfyUI RSS: %.2f GB\n", $1/1048576}' \
                  || echo "未运行" ;;
  *) echo "用法: $0 {start [参数]|lowmem|stop|restart|status|mem|log [行数]}"; exit 1 ;;
esac
