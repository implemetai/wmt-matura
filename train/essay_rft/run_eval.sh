#!/bin/bash
# Essay RFT eval on the L40S, own servers only: Bielik-4.5B-v3 Q8_0 + the essay adapter loaded at scale 0
# (--lora-init-without-apply) :18330 (-np 1, --cache-ram 0), reranker :18092 (shared) if it answers /health else own
# :18332, harness v3 :18333 with the final flags (CKE_MODE=1 QTYPE_V2=1 RERANK=1 DENSE=0 ESSAY_SAFE=1, default essay
# temperature / seed) + CKE_LORA_TYPES=essay CKE_LORA_SCALE=1 (adapter at scale 1 for essay-flow calls only).
#   ADAPTER=/scratch/essay_rft/loras/x.gguf bash train/essay_rft/run_eval.sh
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
ADAPTER=${ADAPTER:?set ADAPTER}
SYSTEM=${SYSTEM:-rft}
mkdir -p $O
LOG=$O/eval
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
  "$LS" -m "$RERANKER" --reranking --host 127.0.0.1 --port 18332 -ngl 999 -c 8192 -b 4096 -ub 4096 -np 1 \
    --cache-ram 0 --no-webui --alias bge-reranker-v2-m3 > "$LOG-rerank.log" 2>&1 < /dev/null &
  RPID=$!; PIDS+=($RPID); RER=http://127.0.0.1:18332
  wait_up $RER $RPID || { echo "reranker failed"; exit 1; }
fi
"$LS" -m "$BIELIK" --lora "$ADAPTER" --lora-init-without-apply --host 127.0.0.1 --port 18330 -ngl 999 -c 16384 -np 1 \
  -fa on --jinja --cache-ram 0 --no-webui --metrics --alias bielik-4.5b-v3 > "$LOG-bielik.log" 2>&1 < /dev/null &
BPID=$!; PIDS+=($BPID)
wait_up http://127.0.0.1:18330 $BPID || { tail -20 "$LOG-bielik.log"; exit 1; }
# b11185 keeps scale 1 after --lora-init-without-apply (lora_default_test.sh): set the global scale to 0 (the harness
# sends scale 1 explicitly for essay-flow calls). The 27.09 00:40 eval ran without this line; essay calls were
# explicit scale 1 either way, so its essays are the same.
[ "${GLOBAL_ZERO:-1}" = 1 ] && curl -s -m 10 -X POST http://127.0.0.1:18330/lora-adapters -H 'Content-Type: application/json' \
  -d '[{"id":0,"scale":0.0}]' >/dev/null
IMG_DESC_NO_QUERY=1 HARNESS_PORT=18333 SNAPSHOT_KB=0 KB_INDEX_DIR=/scratch/kb_index \
  LLM_BASE_URL=http://127.0.0.1:18330/v1 BASE_LLM_BASE_URL=http://127.0.0.1:18330/v1 LLM_MODEL=bielik-4.5b-v3 \
  CKE_MODE=1 QTYPE_V2=1 RERANK=1 DENSE=0 RERANK_URL=$RER ESSAY_SAFE=1 \
  CKE_LORA_TYPES=essay CKE_LORA_SCALE=1 ESSAY_LOG_CALLS=$O/eval_calls_$SYSTEM.jsonl \
  LLM_CONCURRENCY=2 LLM_TIMEOUT=1200 REQUEST_LOG=$LOG-harness-requests.jsonl \
  "$PY" -m harness > "$LOG-harness.log" 2>&1 < /dev/null &
HPID=$!; PIDS+=($HPID)
wait_up http://127.0.0.1:18333 $HPID || { tail -30 "$LOG-harness.log"; exit 1; }
curl -s -m 10 http://127.0.0.1:18333/health | "$PY" -c 'import json,sys; c=json.load(sys.stdin).get("config",{}); print("harness config:", {k: c.get(k) for k in ("cke_mode","qtype_v2","rerank","dense","essay_safe","essay_temperature","essay_seed","cke_lora_types","cke_lora_scale")})'

"$PY" train/essay_rft/eval_rft.py --llm http://127.0.0.1:18330 --harness http://127.0.0.1:18333 \
  --out $O/answers_$SYSTEM.jsonl --system $SYSTEM
echo "$(date +%T) ALL_DONE"
