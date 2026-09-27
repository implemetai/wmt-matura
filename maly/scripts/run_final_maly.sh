#!/bin/bash
# run_final_maly.sh PKG_DIR OUT_DIR  --  final exam runner for "Mały, ale wariat" (team Vibers)
#
# Answering model: a quantized Bielik-4.5B-v3.0-Instruct GGUF given in env GGUF. Fully offline: only 127.0.0.1.
# This system has NO vision model: images stay as '[Obraz: images/X.png]' placeholders (no image descriptions).
#
#   GGUF=/workspace/maly/models/Bielik-4.5B-v3-Istruct-ungated.i1-Q4_K_M.gguf MODE=hybrid \
#     bash /workspace/maly/run_final_maly.sh PKG_DIR OUT_DIR
#   (long run over ssh: setsid nohup env GGUF=... MODE=... bash run_final_maly.sh PKG OUT > LOG 2>&1 < /dev/null &)
#
#   MODE=raw     one llama-server with GGUF (-c 16384 -np 1 -fa on --jinja --cache-ram 0, as in the quant evals);
#                every item -> harness.exam_runner --mode raw --concurrency 1 (one user message, no system, T=0)
#   MODE=hybrid  short items as raw; the essay goes through harness v3 (CKE_MODE=1 QTYPE_V2=1 RERANK=1 DENSE=0,
#                bge-reranker-v2-m3 + BM25 plwiki KB) = scripts/run_final.sh steps 4-6 minus the vision model
#
# PKG_DIR = exam.json + answers-template.json + images/.  OUT_DIR gets answers.json, debug.jsonl, run_info.txt, logs/.
# Work files go to local /scratch first and are copied to OUT_DIR at the end (the /workspace network FS had a write
# outage). Re-running with the same OUT_DIR resumes from OUT_DIR/debug.jsonl; use a fresh OUT_DIR for a clean run.
# Items still empty after the main pass (e.g. harness essay timeout) get one retry in raw mode.
# Before starting anything on GPU it waits for >= MIN_RAM_GB available RAM (free -g) and >= MIN_VRAM_MB free VRAM,
# re-checking every 2 min for up to WAIT_MIN min; then it exits 3 without starting anything.
#
# Env (defaults): GGUF (required), MODE (raw), CODE (/workspace/maly/code: harness + kb, the version with --mode hybrid),
#   PY (/workspace/venvs/wmt/bin/python), LS (/workspace/opt/llama/current/llama-server),
#   RERANKER (/workspace/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf), KB_INDEX_DIR (from /workspace/env.sh),
#   LLM_PORT/RER_PORT/H_PORT (18410/18411/18412), CTX (16384), H_CONC (2 = harness LLM concurrency, as run_final.sh),
#   MIN_RAM_GB (10), MIN_VRAM_MB (8192), WAIT_MIN (20), WORK_ROOT (/scratch/maly/work), LOG_ROOT (/scratch/maly/logs)
# Stops only the processes it started. Exit: 0 valid, 1 error/invalid, 2 usage, 3 not enough free RAM/VRAM.
set -u
USAGE="usage: GGUF=/path/quant.gguf MODE=raw|hybrid $0 PKG_DIR OUT_DIR"
PKG=${1:?$USAGE}; OUT=${2:?$USAGE}
GGUF=${GGUF:?$USAGE}
MODE=${MODE:-raw}
RERANK=${RERANK:-1}   # hybrid: 1 = bge-reranker + BM25 (graded config), 0 = BM25 only (no second model)
case "$MODE" in raw|hybrid) ;; *) echo "$USAGE" >&2; exit 2;; esac
PKG=$(cd "$PKG" && pwd) || exit 2
mkdir -p "$OUT" && OUT=$(cd "$OUT" && pwd) || exit 2
GGUF=$(readlink -f "$GGUF")

CODE=${CODE:-/workspace/maly/code}
PY=${PY:-/workspace/venvs/wmt/bin/python}
LS=${LS:-/workspace/opt/llama/current/llama-server}
RERANKER=${RERANKER:-/workspace/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf}
if [ -z "${KB_INDEX_DIR:-}" ] && [ -f /workspace/env.sh ]; then
  KB_INDEX_DIR=$(bash -c 'source /workspace/env.sh >/dev/null 2>&1; echo "${KB_INDEX_DIR:-}"')
fi
KB_INDEX_DIR=${KB_INDEX_DIR:-/workspace/kb_data/index}
LLM_PORT=${LLM_PORT:-18410}; RER_PORT=${RER_PORT:-18411}; H_PORT=${H_PORT:-18412}
DEAD_PORT=18419   # DENSE_URL points here (DENSE=0, never contacted; keeps the harness off other people's default ports)
CTX=${CTX:-16384}; H_CONC=${H_CONC:-2}
MIN_RAM_GB=${MIN_RAM_GB:-10}; MIN_VRAM_MB=${MIN_VRAM_MB:-8192}; WAIT_MIN=${WAIT_MIN:-20}
ALIAS=bielik-4.5b-v3
QUANT=$(basename "$GGUF" .gguf); QUANT=${QUANT##*.}; QUANT=${QUANT#i1-}
SYSNAME=bielik45-$QUANT-$MODE-noimg
EXAM=$PKG/exam.json
TS=$(date +%Y%m%d-%H%M%S)
WORK_ROOT=${WORK_ROOT:-/scratch/maly/work}; LOG_ROOT=${LOG_ROOT:-/scratch/maly/logs}
if ! { mkdir -p "$WORK_ROOT" "$LOG_ROOT" 2>/dev/null && [ -w "$WORK_ROOT" ] && [ -w "$LOG_ROOT" ]; }; then
  WORK_ROOT=$OUT/.work; LOG_ROOT=$OUT/logs; mkdir -p "$WORK_ROOT" "$LOG_ROOT"
fi
WORK=$WORK_ROOT/$(basename "$OUT")-$TS; mkdir -p "$WORK"
LOG=$LOG_ROOT/final-maly-$QUANT-$MODE-$TS
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null; done; sleep 2
            for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill -9 "$p" 2>/dev/null; done; }
trap cleanup EXIT
trap 'exit 130' INT TERM
say() { echo "$(date +%T) $*"; }
die() { say "FINAL-MALY ERROR: $*"; exit 1; }
wait_up() {  # $1 url, $2 pid, $3 name
  local t0; t0=$(date +%s)
  for i in $(seq 1 600); do
    curl -sf -m 5 "$1/health" >/dev/null 2>&1 && { say "$3 up after $(( $(date +%s) - t0 ))s ($1)"; return 0; }
    kill -0 "$2" 2>/dev/null || return 1
    sleep 1
  done; return 1
}
port_free() {
  if ss -Hltn "sport = :$1" 2>/dev/null | grep -q . || curl -s -m 2 "http://127.0.0.1:$1/health" >/dev/null 2>&1; then
    die "port $1 already in use"; fi
}
RAM_AV=0; VRAM_FREE=0
res_ok() {
  RAM_AV=$(free -g | awk '/^Mem:/{print $7}')
  VRAM_FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
  [ -n "$VRAM_FREE" ] || VRAM_FREE=0
  [ "$RAM_AV" -ge "$MIN_RAM_GB" ] && [ "$VRAM_FREE" -ge "$MIN_VRAM_MB" ]
}
wait_resources() {
  local deadline=$(( $(date +%s) + WAIT_MIN * 60 ))
  while :; do
    if res_ok; then say "resources OK: RAM available ${RAM_AV} GB (need ${MIN_RAM_GB}), free VRAM ${VRAM_FREE} MiB (need ${MIN_VRAM_MB})"; return 0; fi
    say "resources LOW: RAM available ${RAM_AV} GB (need ${MIN_RAM_GB}), free VRAM ${VRAM_FREE} MiB (need ${MIN_VRAM_MB})"
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 120
  done
}
monitor() {  # $@ = "name:pid" ... ; one line every 5 s: available RAM, used VRAM, RSS per process
  while :; do
    local line="$(date +%T) avail_mb=$(free -m | awk '/^Mem:/{print $7}') vram_used_mb=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')"
    for np in "$@"; do
      local kb; kb=$(ps -o rss= -p "${np#*:}" 2>/dev/null | tr -d ' '); line="$line ${np%%:*}_rss_mb=$(( ${kb:-0} / 1024 ))"
    done
    echo "$line"; sleep 5
  done
}

T_START=$(date +%s)
say "run_final_maly: MODE=$MODE pack=$PKG -> $OUT (work $WORK, logs $LOG-*)"
say "GGUF $GGUF ($(stat -c %s "$GGUF" 2>/dev/null) bytes)"
SHA=$(sha256sum "$GGUF" 2>/dev/null | cut -d' ' -f1)
say "sha256sum: $SHA  $GGUF"

# ---- preflight
for f in "$LS" "$PY" "$GGUF" "$EXAM" "$PKG/answers-template.json" "$CODE/harness/exam_runner.py"; do
  [ -e "$f" ] || die "missing $f"
done
[ -d "$PKG/images" ] || say "WARNING: $PKG/images missing"
if [ "$MODE" = hybrid ]; then
  grep -q '"hybrid"' "$CODE/harness/exam_runner.py" || die "$CODE/harness/exam_runner.py has no --mode hybrid"
  [ "$RERANK" = 0 ] || [ -e "$RERANKER" ] || die "missing $RERANKER"
  [ -f "$KB_INDEX_DIR/tokenizer.json" ] || die "missing KB index $KB_INDEX_DIR"
  for p in $LLM_PORT $RER_PORT $H_PORT; do port_free $p; done
else
  port_free $LLM_PORT
fi
if [ -s "$OUT/debug.jsonl" ]; then cp "$OUT/debug.jsonl" "$WORK/debug.jsonl" && say "resuming from $OUT/debug.jsonl"; fi
wait_resources || { say "FINAL-MALY: not enough free RAM/VRAM after ${WAIT_MIN} min, nothing started"; exit 3; }
free -m | sed 's/^/    /'

# ---- servers
"$LS" -m "$GGUF" --host 127.0.0.1 --port $LLM_PORT -ngl 999 -c $CTX -np 1 -fa on --jinja \
  --cache-ram 0 --no-webui --metrics --alias $ALIAS > "$LOG-llm.log" 2>&1 < /dev/null &
LPID=$!; PIDS+=($LPID); MON_ARGS=("llm:$LPID")
if [ "$MODE" = hybrid ] && [ "$RERANK" = 1 ]; then
  "$LS" -m "$RERANKER" --reranking --host 127.0.0.1 --port $RER_PORT -ngl 999 -c 8192 -b 4096 -ub 4096 -np 1 \
    --cache-ram 0 --no-webui --alias bge-reranker-v2-m3 > "$LOG-rerank.log" 2>&1 < /dev/null &
  RPID=$!; PIDS+=($RPID); MON_ARGS+=("rerank:$RPID")
fi
wait_up http://127.0.0.1:$LLM_PORT $LPID llama-server || { tail -20 "$LOG-llm.log"; die "llama-server did not start"; }
if [ "$MODE" = hybrid ]; then
  if [ "$RERANK" = 1 ]; then wait_up http://127.0.0.1:$RER_PORT $RPID reranker || { tail -20 "$LOG-rerank.log"; die "reranker did not start"; }; fi
  T_H=$(date +%s)
  ( cd "$CODE" && exec env IMG_DESC_NO_QUERY=1 HARNESS_HOST=127.0.0.1 HARNESS_PORT=$H_PORT SNAPSHOT_KB=0 \
      KB_INDEX_DIR="$KB_INDEX_DIR" LLM_BASE_URL=http://127.0.0.1:$LLM_PORT/v1 BASE_LLM_BASE_URL=http://127.0.0.1:$LLM_PORT/v1 \
      LLM_MODEL=$ALIAS CKE_MODE=1 QTYPE_V2=1 RERANK=$RERANK DENSE=0 RERANK_URL=http://127.0.0.1:$RER_PORT \
      DENSE_URL=http://127.0.0.1:$DEAD_PORT LLM_CONCURRENCY=$H_CONC LLM_TIMEOUT=1200 \
      REQUEST_LOG="$LOG-harness-requests.jsonl" "$PY" -m harness ) > "$LOG-harness.log" 2>&1 < /dev/null &
  HPID=$!; PIDS+=($HPID); MON_ARGS+=("harness:$HPID")
  wait_up http://127.0.0.1:$H_PORT $HPID harness+KB || { tail -30 "$LOG-harness.log"; die "harness did not start"; }
  H_UP=$(( $(date +%s) - T_H ))
  curl -s -m 10 http://127.0.0.1:$H_PORT/health > "$LOG-harness-health.json"
  "$PY" - "$LOG-harness-health.json" <<'PYEOF' || die "harness health check failed (see $LOG-harness-health.json)"
import json, sys
h = json.load(open(sys.argv[1], encoding="utf-8"))
kb, cfg = h.get("kb") or {}, h.get("config") or {}
print(f"    harness: llm_ok={h.get('llm_ok')} kb_available={kb.get('available')} index={kb.get('index_dir')} "
      f"reranker={kb.get('reranker')} dense_loaded={(kb.get('dense') or {}).get('loaded')}")
print("    config: " + ", ".join(f"{k}={cfg[k]}" for k in sorted(cfg) if k in (
    "cke_mode", "qtype_v2", "rerank", "rerank_url", "dense", "llm_base_url", "llm_model", "kb_index_dir")))
sys.exit(0 if h.get("llm_ok") and kb.get("available") else 1)
PYEOF
  grep -h "KB loaded" "$LOG-harness.log" | tail -1 | sed 's/^/    /'
fi
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null \
  | grep -E "^($(IFS='|'; echo "${PIDS[*]}"))," | sed 's/^/    VRAM pid,MiB: /'
monitor "${MON_ARGS[@]}" > "$LOG-mon.log" 2>&1 < /dev/null &
PIDS+=($!)

# ---- answer the exam (no --image-desc: PNG placeholders only)
cd "$CODE" || die "no $CODE"
T_RUN=$(date +%s)
"$PY" -m harness.exam_runner "$EXAM" --mode $MODE --llm-url http://127.0.0.1:$LLM_PORT --url http://127.0.0.1:$H_PORT \
  --model $ALIAS --concurrency 1 --timeout 1800 --system-name "$SYSNAME" --out "$WORK/answers.json" 2>&1 | tee "$LOG-runner.log"
[ -s "$WORK/answers.json" ] || die "exam_runner wrote no answers.json (see $LOG-runner.log)"
EMPTY=$("$PY" -c "import json,sys; a=json.load(open(sys.argv[1],encoding='utf-8'))['answers']; print(','.join(x['id'] for x in a if not x['answer'].strip()))" "$WORK/answers.json")
if [ -n "$EMPTY" ]; then
  say "empty answers after the main pass: $EMPTY -> one retry in raw mode"
  "$PY" -m harness.exam_runner "$EXAM" --mode raw --llm-url http://127.0.0.1:$LLM_PORT --model $ALIAS --ids "$EMPTY" \
    --concurrency 1 --timeout 1800 --system-name "$SYSNAME-retry" --out "$WORK/answers.json" 2>&1 | tee -a "$LOG-runner.log"
fi
T_ANS=$(( $(date +%s) - T_RUN ))

# ---- validate, essay sanity, resource summary
"$PY" -m harness.exam_runner --validate "$WORK/answers.json" --exam "$EXAM" 2>&1 | tee "$LOG-validate.log"
VALID=0; grep -q '^VALID' "$LOG-validate.log" && VALID=1
"$PY" - "$EXAM" "$WORK/answers.json" <<'PYEOF' 2>&1 | tee -a "$LOG-validate.log"
import json, re, sys
from harness.exam_runner import spec_for
exam = json.load(open(sys.argv[1], encoding="utf-8"))
ans = {a["id"]: a["answer"] for a in json.load(open(sys.argv[2], encoding="utf-8"))["answers"]}
print(f"answered {sum(1 for v in ans.values() if v.strip())}/{len(ans)}")
for it in exam["items"]:
    if spec_for(it)["kind"] == "essay":
        t = ans.get(it["id"], "")
        lines = [l for l in t.splitlines() if l.strip()]
        bullets = sum(1 for l in lines if re.match(r"\s*([-*•]|\d+[.)])\s", l))
        first = lines[0][:80] if lines else ""
        print(f"ESSAY {it['id']}: {len(t.split())} words, {len(lines)} non-empty lines, "
              f"{bullets} bullet/numbered lines, first line: {first!r}")
PYEOF
if [ -s "$LOG-mon.log" ]; then
  awk '{for(i=2;i<=NF;i++){split($i,a,"="); v=a[2]+0; if(a[1]=="avail_mb"){if(!mn||v<mn)mn=v} else if(v>m[a[1]])m[a[1]]=v}}
       END{printf "peak:"; for(k in m) printf " %s=%d", k, m[k]; printf " min_avail_mb=%d\n", mn}' "$LOG-mon.log" \
    | sed "s/^/$(date +%T) /"
fi
T_ALL=$(( $(date +%s) - T_START ))

# ---- copy results from /scratch to OUT_DIR, write run_info
{
  echo "date: $(date -u +%FT%TZ)"
  echo "system: $SYSNAME (mode $MODE, no image descriptions, fully offline)"
  echo "gguf: $GGUF"
  echo "sha256: $SHA"
  echo "llama-server: $("$LS" --version 2>&1 | grep -m1 version); flags -ngl 999 -c $CTX -np 1 -fa on --jinja --cache-ram 0; T=0"
  if [ "$MODE" = hybrid ]; then
    echo "harness: CKE_MODE=1 QTYPE_V2=1 RERANK=$RERANK DENSE=0 LLM_CONCURRENCY=$H_CONC KB=$KB_INDEX_DIR reranker=$RERANKER; up in ${H_UP}s"
  fi
  echo "code: $CODE (exam_runner md5 $(md5sum "$CODE/harness/exam_runner.py" | cut -d' ' -f1))"
  echo "pack: $PKG"
  echo "answer time: ${T_ANS}s; total wall: ${T_ALL}s; valid: $VALID"
} > "$WORK/run_info.txt"
mkdir -p "$OUT/logs"
if cp -f "$WORK/answers.json" "$WORK/debug.jsonl" "$WORK/run_info.txt" "$OUT/" && cp -f "$LOG"-* "$OUT/logs/"; then
  FINAL=$OUT/answers.json
else
  say "WARNING: copy to $OUT failed, results stay in $WORK"; FINAL=$WORK/answers.json
fi
say "answer time ${T_ANS}s, total wall ${T_ALL}s"
[ "$VALID" = 1 ] || die "answers.json NOT valid, see $LOG-validate.log ($FINAL)"
say "done"
echo "ANSWERS: $FINAL"
