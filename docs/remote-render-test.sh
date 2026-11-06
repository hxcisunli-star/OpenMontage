#!/usr/bin/env bash
# Acceptance test (round 3) for the remote render channel, run by the USER from the OpenMontage root:
#     bash docs/remote-render-test.sh 2>&1 | tee projects/c-recursion-cn/renders/remote_test_report.txt
#   plus the full-lesson automatic render (about 5-30 minutes depending on the machine):
#     FULL=1 bash docs/remote-render-test.sh 2>&1 | tee projects/c-recursion-cn/renders/remote_test_report.txt
#   before the agent has delivered src_overlay / fontconfig_self_managed (pictures WILL differ; plumbing and speed only):
#     ALLOW_DRIFT=1 bash docs/remote-render-test.sh ...
# Compares remote vs local renders of lesson 16 (PSNR + SSIM) and times: one board by number of render processes, four boards queued together,
# and (FULL=1) the whole lesson in the default automatic mode.  The local chunk cache is restored afterwards.
# Nothing here reads keys; the client uses its own configured identity.
set -uo pipefail
P=projects/c-recursion-cn; R=$P/renders; T=$R/remote_test; PY=.venv/bin/python
STILLS="6 120 153.3 158 290.8 336"          # hand font, mono rows + arrows (K4), long code lines (K7), quiz board (K8)
ALLOW=""; [ "${ALLOW_DRIFT:-0}" = "1" ] && ALLOW="--allow-drift"
LOCAL_BASELINE_S=1625                         # whole lesson, this machine, multi-process (measured)
mkdir -p "$T/local" "$T/remote"
rm -rf "$T/chunks_backup"; cp -a $R/chunks "$T/chunks_backup" 2>/dev/null   # rm first: cp -a into an existing dir would nest and later restore a stale copy
restore() { rm -rf $R/chunks; cp -a "$T/chunks_backup" $R/chunks; echo "(local chunk cache restored)"; }
trap restore EXIT

metrics() {  # a b -> "PSNR avg:xx  SSIM All:yy"
  local p s
  p=$(ffmpeg -hide_banner -nostats -i "$1" -i "$2" -lavfi "[0:v][1:v]psnr;[0:v][1:v]ssim" -f null - 2>&1)
  echo "$(echo "$p" | grep -o "average:[^ ]*" | head -1)  $(echo "$p" | grep -o "All:[0-9.]*" | head -1)"
}
t() { date +%s; }

echo "== 1. probe (auto mode needs features src_overlay + fontconfig_self_managed; the agent's best settings are render_profile / capacity)"
python3 tools/video/remote_cpu_render.py probe || { echo "PROBE FAILED"; exit 1; }

echo "== 2. stills: local vs remote  (CPU path: PSNR >= 50; GPU path: PSNR >= 45 and SSIM >= 0.995)"
rm -f "$T"/local/*.png "$T"/remote/*.png; touch "$T/.m1"
$PY docs/whiteboard_render.py $P --local --stills $STILLS >/dev/null || { echo "local stills failed"; exit 1; }
find $R/stills -newer "$T/.m1" -name 't*.png' -exec cp {} "$T/local/" \;
touch "$T/.m2"; s=$(t)
$PY docs/whiteboard_render.py $P --remote-cpu $ALLOW --stills $STILLS || { echo "remote stills failed"; exit 1; }
echo "remote stills (6) took $(( $(t) - s )) s"
find $R/stills -newer "$T/.m2" -name 't*.png' -exec cp {} "$T/remote/" \;
for f in "$T"/local/*.png; do printf "%s  " "$(basename "$f")"; metrics "$f" "$T/remote/$(basename "$f")"; done

echo "== 3. board K4 (1579 frames) on the remote machine, by number of render processes (workers x 2 tabs); local multi-process was ~225 s"
K4_LOCAL=$(ls $R/chunks/K4-*.mp4 | head -1)
for W in 1 4 8 16; do
  s=$(t)
  $PY docs/whiteboard_render.py $P --remote-cpu $ALLOW --workers $W --force K4 --only K4 --keep-old >"$T/out_w$W.txt" 2>&1 \
    || { echo "remote K4 failed with workers=$W"; tail -5 "$T/out_w$W.txt"; break; }
  echo "workers $W: K4 in $(( $(t) - s )) s (incl. upload/download)"
  cp "$K4_LOCAL" "$T/K4_remote_w$W.mp4"; cp "$T/chunks_backup/$(basename "$K4_LOCAL")" "$K4_LOCAL"
done
LAST=$(ls -t "$T"/K4_remote_w*.mp4 2>/dev/null | head -1)
[ -n "$LAST" ] && { printf "K4 remote (last run) vs local original (CPU path min >= 45 dB; GPU path min >= 42, avg >= 45):  "; metrics "$LAST" "$T/chunks_backup/$(basename "$K4_LOCAL")"; }

echo "== 4. four boards queued together (the agent may run several jobs at once)"
s=$(t)
$PY docs/whiteboard_render.py $P --remote-cpu $ALLOW --force K1,K2,K3,K4 --only K1,K2,K3,K4 --keep-old >"$T/out_multi.txt" 2>&1 \
  && echo "K1..K4 (4 jobs queued) took $(( $(t) - s )) s" || { echo "multi-board run failed"; tail -5 "$T/out_multi.txt"; }
restore; trap restore EXIT

if [ "${FULL:-0}" = "1" ]; then
  echo "== 5. FULL lesson, default automatic mode (no flags): backend choice, upload, queue, bring back, join, mux; local multi-process baseline = ${LOCAL_BASELINE_S} s"
  s=$(t)
  $PY docs/whiteboard_render.py $P --final --force K1,K2,K3,K4,K5,K6,K7,K8 --keep-old --out renders/remote_test/final_auto.mp4 >"$T/out_full.txt" 2>&1 \
    && { e=$(( $(t) - s )); echo "whole lesson: $e s  (local baseline $LOCAL_BASELINE_S s, target < $(( LOCAL_BASELINE_S / 2 )) s)"; grep -E "render backend|remote:|success" "$T/out_full.txt" | head -20
         printf "final_auto vs local final_par_local:  "; metrics "$T/final_auto.mp4" "$R/final_par_local.mp4"; } \
    || { echo "full run failed"; tail -8 "$T/out_full.txt"; }
fi
echo "== done; report: $R/remote_test_report.txt"
