#!/usr/bin/env bash
# Read-only environment probe for remote rendering.
# Changes nothing, reads no secrets or credentials. The only network use is the two optional reachability
# checks at the end (no data is sent); set SKIP_NET=1 to skip them.
# Usage:  bash remote-render-probe.sh 2>&1 | tee probe_output.txt
set -u

echo "== host"
uname -a; uname -m
head -3 /etc/os-release 2>/dev/null
ldd --version 2>/dev/null | head -1

echo "== cpu / memory / load"
nproc
free -m | head -2
uptime
cat /proc/pressure/cpu 2>/dev/null || true

echo "== disk (home) and working dir"
df -h "$HOME" | tail -1
echo "HOME=$HOME"

echo "== tools"
tool() {  # name, version-flag
  printf "%s: " "$1"
  if command -v "$1" >/dev/null 2>&1; then
    printf "%s  " "$(command -v "$1")"
    if [ -n "${2:-}" ]; then "$1" $2 2>&1 | head -1; else echo; fi
  else
    echo MISSING
  fi
}
tool node --version; tool npm --version; tool npx --version
tool ffmpeg -version; tool ffprobe -version
tool tmux -V; tool nohup --version; tool rsync --version; tool scp ""; tool curl --version

echo "== chrome shared libs (Ubuntu names; MISSING = please install or tell us)"
for l in libnss3 libatk-1.0 libatk-bridge-2.0 libcups libdrm libxkbcommon libXcomposite libXdamage libXfixes libXrandr libgbm libasound libpango-1.0 libcairo; do
  printf "%s: " "$l"
  if ldconfig -p 2>/dev/null | grep -q "$l"; then echo ok; else echo MISSING; fi
done

echo "== fonts (families installed; we need to know whether any CJK fonts exist)"
if command -v fc-list >/dev/null 2>&1; then fc-list : family 2>/dev/null | sort -u | head -80; else echo "no fontconfig tools (fc-list)"; fi

echo "== limits"
ulimit -a | grep -E "processes|open files|virtual memory|max memory" || true
echo "systemd --user: $(systemctl --user is-system-running 2>&1 | head -1)"

echo "== ssh server (what we would connect to)"
(ss -ltn 2>/dev/null | grep -E ":22 ") || echo "port 22 not listed (maybe another port)"

if [ "${SKIP_NET:-0}" != "1" ]; then
  echo "== optional reachability (no data sent)"
  for u in https://registry.npmjs.org/ https://storage.googleapis.com/; do
    printf "%s: " "$u"
    curl -sS -m 8 -o /dev/null -w "%{http_code}\n" "$u" 2>&1 || echo FAIL
  done
fi
echo "== done"
