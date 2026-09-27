#!/bin/bash
# hybrid essays from local /scratch only: essays3.sh TAG GGUF N
TAG=$1; G=$2; N=${3:-2}
export CODE=/scratch/maly/code PY=/scratch/mock/wmt-matura/.venv/bin/python LS=/scratch/ovl/opt/llama/current/llama-server \
  RERANKER=/scratch/ovl/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf KB_INDEX_DIR=/scratch/kb_index
for k in $(seq 1 $N); do
  GGUF=$G MODE=hybrid bash /scratch/maly/run_final_maly.sh /scratch/maly/essay_pack /scratch/maly/runs_essays/$TAG-hybrid-r$k
  GGUF=$G MODE=hybrid bash /scratch/maly/run_final_maly.sh /scratch/maly/code/data_cke/mock2023 /scratch/maly/runs_final/$TAG-hybrid-r$((k+1))
done
cp -r /scratch/maly/runs_essays /scratch/maly/runs_final /workspace/maly/ 2>/dev/null
echo ESSAYS_DONE
