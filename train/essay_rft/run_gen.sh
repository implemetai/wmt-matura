#!/bin/bash
# Essay RFT sampling on the L40S, own servers only: untouched Bielik-4.5B-v3 Q8_0 (no LoRA) :18330 (-np 4,
# --cache-ram 0), reranker :18092 (shared) if it answers /health else own :18332, harness v3 :18333
# (CKE_MODE=1 QTYPE_V2=1 RERANK=1 DENSE=0 ESSAY_SAFE=1, ESSAY_TEMPERATURE=0.7, ESSAY_SEED=-1, ESSAY_LOG_CALLS).
# Mirror /scratch/essay_rft/wmt-matura. Stops only what it started (trap on exit). Args go to gen_essays.py.
#   bash train/essay_rft/run_gen.sh [--limit 2 --n 2]
set -u
R=/scratch/essay_rft/wmt-matura
O=/scratch/essay_rft/out
cd $R
LS=/scratch/ovl/opt/llama/current/llama-server
BIELIK=/scratch/ovl/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf
RERANKER=/scratch/ovl/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf
PY=/scratch/ovl/venvs/wmt/bin/python
# keep every process off the NFS /workspace (the harness on the /workspace venv died with a Bus error on 26.09)
export HOME=/scratch/ovl/home HF_HOME=/scratch/ovl/hf PYTHONNOUSERSITE=1
mkdir -p $O
LOG=$O/gen
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null; done; sleep 3
            for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill -9 "$p" 2>/dev/null; done; echo "$(date +%T) stopped ${PIDS[*]:-}"; }
trap cleanup EXIT
trap 'exit 130' INT TERM
wait_up() { for i in $(seq 1 600); do curl -sf "$1/health" >/dev/null 2>&1 && { echo "$(date +%T) up $1 ${i}s"; return 0; }
            kill -0 "$2" 2>/dev/null || return 1; sleep 1; done; return 1; }
for p in 18330 18332 18333; do curl -s -m 2 http://127.0.0.1:$p/health >/dev/null 2>&1 && { echo "port $p busy"; exit 1; }; done

if curl -sf -m 3 http://127.0.0.1:18092/health >/dev/null 2>&1; then
  RER=http://127.0.0.1:18092; echo "reranker: shared :18092"
else
  "$LS" -m "$RERANKER" --reranking --host 127.0.0.1 --port 18332 -ngl 999 -c 8192 -b 4096 -ub 4096 -np 2 \
    --cache-ram 0 --no-webui --alias bge-reranker-v2-m3 > "$LOG-rerank.log" 2>&1 < /dev/null &
  RPID=$!; PIDS+=($RPID); RER=http://127.0.0.1:18332
  wait_up $RER $RPID || { echo "reranker failed"; exit 1; }
fi
"$LS" -m "$BIELIK" --host 127.0.0.1 --port 18330 -ngl 999 -c 40960 -np 4 -fa on --jinja \
  --cache-ram 0 --no-webui --metrics --alias bielik-4.5b-v3 > "$LOG-bielik.log" 2>&1 < /dev/null &
BPID=$!; PIDS+=($BPID)
wait_up http://127.0.0.1:18330 $BPID || { tail -20 "$LOG-bielik.log"; exit 1; }
IMG_DESC_NO_QUERY=1 HARNESS_PORT=18333 SNAPSHOT_KB=0 KB_INDEX_DIR=/scratch/kb_index \
  LLM_BASE_URL=http://127.0.0.1:18330/v1 BASE_LLM_BASE_URL=http://127.0.0.1:18330/v1 LLM_MODEL=bielik-4.5b-v3 \
  CKE_MODE=1 QTYPE_V2=1 RERANK=1 DENSE=0 RERANK_URL=$RER ESSAY_SAFE=1 \
  ESSAY_TEMPERATURE=0.7 ESSAY_SEED=-1 ESSAY_LOG_CALLS=${CALLS:-$O/calls.jsonl} \
  LLM_CONCURRENCY=8 LLM_TIMEOUT=1200 REQUEST_LOG=$LOG-harness-requests.jsonl \
  "$PY" -m harness > "$LOG-harness.log" 2>&1 < /dev/null &
HPID=$!; PIDS+=($HPID)
wait_up http://127.0.0.1:18333 $HPID || { tail -30 "$LOG-harness.log"; exit 1; }
curl -s -m 10 http://127.0.0.1:18333/health | "$PY" -c 'import json,sys; c=json.load(sys.stdin).get("config",{}); print("harness config:", {k: c.get(k) for k in ("cke_mode","qtype_v2","rerank","dense","essay_safe","essay_temperature","essay_seed","essay_log_calls","llm_base_url","rerank_url")})'
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader

"$PY" train/essay_rft/gen_essays.py --url http://127.0.0.1:18333 --out ${OUTF:-$O/essays.jsonl} "$@"
echo "$(date +%T) ALL_DONE"
