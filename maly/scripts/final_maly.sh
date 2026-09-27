#!/bin/bash
# final_maly.sh PKG_DIR [OUT_DIR]  --  "Mały, ale wariat" final: Bielik-4.5B-v3 i1-IQ4_XS (2.56 GB) + harness essay.
# Prefers local /scratch copies (the /workspace network FS had write/read outages at night); falls back to /workspace.
# Env: QUANT (IQ4_XS), MODE (hybrid | raw).
set -u
PKG=${1:?usage: final_maly.sh PKG_DIR [OUT_DIR]}
QUANT=${QUANT:-IQ4_XS}
OUT=${2:-/scratch/maly/final/$(basename "$PKG")-$QUANT-$(date +%H%M%S)}
F=Bielik-4.5B-v3-Istruct-ungated.i1-$QUANT.gguf
pick() { for p in "$@"; do [ -e "$p" ] && { echo "$p"; return; }; done; echo "$1"; }
export GGUF=$(pick /scratch/maly/models/$F /workspace/maly/models/$F)
export CODE=$(pick /scratch/maly/code /workspace/maly/code)
export PY=$(pick /scratch/mock/wmt-matura/.venv/bin/python /workspace/venvs/wmt/bin/python)
export LS=$(pick /scratch/ovl/opt/llama/current/llama-server /workspace/opt/llama/current/llama-server)
export RERANKER=$(pick /scratch/ovl/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf /workspace/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf)
export KB_INDEX_DIR=$(pick /scratch/kb_index/tokenizer.json /workspace/kb_data/index/tokenizer.json | xargs dirname)
export MODE=${MODE:-hybrid}
RF=$(pick /scratch/maly/run_final_maly.sh /workspace/maly/run_final_maly.sh)
mkdir -p "$(dirname "$OUT")" 2>/dev/null
echo "final_maly: QUANT=$QUANT MODE=$MODE GGUF=$GGUF CODE=$CODE PY=$PY LS=$LS KB=$KB_INDEX_DIR OUT=$OUT"
exec bash "$RF" "$PKG" "$OUT"
