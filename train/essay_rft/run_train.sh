#!/bin/bash
# Essay RFT, step 4 on the L40S: LoRA on the selected rows (bf16, r16, alpha32, lr 1e-4, 2 epochs, completions-only,
# seed 42) with train/train_lora.py, then train/export.sh (GGUF adapter + size check against the registered base).
# Everything from the local /scratch/ovl mirror (NFS /workspace is flaky); the adapter is copied to /workspace/loras.
#   bash train/essay_rft/run_train.sh [NAME]
set -uo pipefail
S=/scratch/ovl
E=/scratch/essay_rft
NAME=${1:-bielik45-essay-rft-r16-e2}
export HOME=$S/home HF_HOME=$S/hf HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 RUNS_DIR=$E/runs LORA_DIR=$E/loras \
       MODELS_DIR=$S/models LLAMA_DIR=$S/opt/llama/current LLAMA_SRC=$S/opt/llama.cpp-src \
       CONVERT_PY=$S/venvs/convert/bin/python TRAIN_PY=$S/venvs/train/bin/python GLIBC_SHIM=$S/opt/glibc-2.39/lib \
       SCRATCH=/scratch/export
mkdir -p $E/runs $E/loras
cd $E/wmt-matura
echo "$(date +%T) train $NAME on $(wc -l < $E/out/rft_rows.jsonl) rows"
$TRAIN_PY train/train_lora.py --data $E/out/rft_rows.jsonl --eval-frac 0.05 \
  --base speakleash/Bielik-4.5B-v3.0-Instruct --name $NAME --backend auto --r 16 --alpha 32 --lr 1e-4 --epochs 2 \
  --seed 42 --max-seq-len 6144 --too-long drop --batch 2 --grad-accum 8 --logging-steps 2 --gen-eval-n 0 \
  > $E/out/train_$NAME.log 2>&1 || { tail -30 $E/out/train_$NAME.log; echo TRAIN_FAILED; exit 1; }
tail -3 $E/out/train_$NAME.log
bash train/export.sh --run $NAME --base-gguf bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf --name $NAME \
  > $E/out/export_$NAME.log 2>&1 || { tail -30 $E/out/export_$NAME.log; echo EXPORT_FAILED; exit 1; }
tail -8 $E/out/export_$NAME.log
mkdir -p /workspace/loras
for f in $NAME.gguf $NAME.gguf.json; do
  cp $E/loras/$f /workspace/loras/$f.tmp && mv /workspace/loras/$f.tmp /workspace/loras/$f
done
cmp -s $E/loras/$NAME.gguf /workspace/loras/$NAME.gguf && echo "copied to /workspace/loras OK" || echo "COPY VERIFY FAILED"
sha256sum $E/loras/$NAME.gguf
echo "$(date +%T) TRAIN_EXPORT_DONE"
