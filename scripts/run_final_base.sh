#!/bin/bash
# The UNTOUCHED base benchmark on an exam pack: Bielik-4.5B-v3 Q8_0 alone, no harness, no retrieval, no image
# descriptions (image placeholders stay), no LoRA, temperature 0, one sequence at a time. The organizers compute
# progress = trained system - this base.
#
#   scripts/run_final_base.sh PKG_DIR [OUT_DIR]     # default OUT_DIR = submissions/final/<pack>-base
set -u
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
PKG=${1:?usage: scripts/run_final_base.sh PKG_DIR [OUT_DIR]}; PKG=$(cd "$PKG" && pwd) || exit 2
OUT=${2:-$R/submissions/final/$(basename "$PKG")-base}; mkdir -p "$OUT" "$R/logs"; OUT=$(cd "$OUT" && pwd)
LS=${LS:-/scratch/ovl/opt/llama/current/llama-server}
PY=${PY:-$R/.venv/bin/python}; [ -x "$PY" ] || PY=python3
BIELIK=${BIELIK:-/scratch/ovl/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf}
PORT=${BASE_PORT:-18250}
LOG=$R/logs/final-base-$(date +%Y%m%d-%H%M%S)
FINAL_HOME=${FINAL_HOME:-/scratch/final_home}; mkdir -p "$FINAL_HOME" 2>/dev/null || FINAL_HOME=$R/logs/final_home; mkdir -p "$FINAL_HOME"
export HOME=$FINAL_HOME HF_HOME=$FINAL_HOME/hf PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
die() { echo "BASE: $*" >&2; exit 1; }
for f in "$LS" "$BIELIK" "$PKG/exam.json" "$PKG/answers-template.json"; do [ -e "$f" ] || die "missing $f"; done
curl -s -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && die "port $PORT already in use"
"$LS" -m "$BIELIK" --host 127.0.0.1 --port $PORT -ngl 999 -c 16384 -np 1 -fa on --jinja --cache-ram 0 --no-webui \
  --alias bielik-4.5b-v3 > "$LOG-bielik.log" 2>&1 < /dev/null &
BPID=$!; trap 'kill $BPID 2>/dev/null' EXIT
for i in $(seq 1 300); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; kill -0 $BPID 2>/dev/null || die "Bielik did not start (see $LOG-bielik.log)"; sleep 1; done
echo "$(date +%T) base run: $PKG -> $OUT"
"$PY" -m harness.exam_runner "$PKG/exam.json" --mode raw --llm-url http://127.0.0.1:$PORT --model bielik-4.5b-v3 \
  --timeout 900 --concurrency 1 --system-name bielik45-base-raw --out "$OUT/answers.json" 2>&1 | tee "$LOG-runner.log"
"$PY" -m harness.exam_runner --validate "$OUT/answers.json" --exam "$PKG/exam.json" 2>&1 | tee "$LOG-validate.log"
echo "BASE ANSWERS: $OUT/answers.json"
