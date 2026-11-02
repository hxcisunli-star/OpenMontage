#!/bin/bash
# Start / stop / look at the ebook server.  Usage: bash docs/whiteboard/ebook/serve_ctl.sh start|stop|status|restart
# The server's config (address, port, certificate, password hash) is projects/_ebook/local/serve.json (outside git); the process id is kept in projects/_ebook/local/serve.pid.
# Stopping is by process id after checking that the process really is this server (never pkill -f).
cd "$(dirname "$0")/../../.." || exit 1
ROOT=$(pwd); L=$ROOT/projects/_ebook/local; CFG=$L/serve.json; PIDF=$L/serve.pid
alive() { [ -f "$PIDF" ] && P=$(cat "$PIDF") && [ -d "/proc/$P" ] && tr '\0' ' ' < "/proc/$P/cmdline" | grep -q "serve.mjs run"; }
case "$1" in
  start)
    [ -f "$CFG" ] || { echo "no config: run  node docs/whiteboard/ebook/serve.mjs init ...  first"; exit 1; }
    alive && { echo "already running (pid $(cat "$PIDF"))"; exit 0; }
    nohup node "$ROOT/docs/whiteboard/ebook/serve.mjs" run --config "$CFG" >> "$L/server.out" 2>&1 &
    echo $! > "$PIDF"; sleep 1
    alive && echo "started (pid $(cat "$PIDF"))" || { echo "failed to start, see projects/_ebook/local/server.out"; tail -5 "$L/server.out"; exit 1; } ;;
  stop)
    if alive; then kill "$(cat "$PIDF")" && echo "stopped"; rm -f "$PIDF"; else echo "not running"; rm -f "$PIDF"; fi ;;
  status)
    if alive; then P=$(cat "$PIDF"); echo "running (pid $P)"; ss -ltnp 2>/dev/null | grep "pid=$P," | awk '{print "listening on", $4}'
      # a server started before serve.mjs changed still sends the old headers (this once left the in-page Python stuck: the old policy forbade WebAssembly)
      STARTED=$(stat -c %Y "/proc/$P" 2>/dev/null); CHANGED=$(stat -c %Y "$ROOT/docs/whiteboard/ebook/serve.mjs")
      [ -n "$STARTED" ] && [ "$CHANGED" -gt "$STARTED" ] && echo "WARNING: serve.mjs is newer than this running server: run  bash docs/whiteboard/ebook/serve_ctl.sh restart"
    else echo "not running"; fi ;;
  restart) bash "$0" stop; bash "$0" start ;;
  *) echo "usage: $0 start|stop|status|restart"; exit 2 ;;
esac
