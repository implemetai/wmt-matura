#!/bin/bash
# Fetch candidate GGUFs for "Mały, ale wariat" into /workspace/maly/models (persistent).
set -u
cd /workspace/maly/models
MR=mradermacher/Bielik-4.5B-v3-Istruct-ungated-i1-GGUF
for q in IQ2_M IQ3_XXS Q3_K_M Q4_K_M; do
  f=Bielik-4.5B-v3-Istruct-ungated.i1-$q.gguf
  [ -s "$f" ] || hf download $MR $f --local-dir . >> ../logs/fetch.log 2>&1 && echo "OK $f" >> ../logs/fetch.log
done
hf download unsloth/Qwen3-4B-Instruct-2507-GGUF Qwen3-4B-Instruct-2507-Q4_K_M.gguf --local-dir . >> ../logs/fetch.log 2>&1 && echo "OK qwen" >> ../logs/fetch.log
sha256sum *.gguf > SHA256SUMS
echo FETCH_DONE >> ../logs/fetch.log
