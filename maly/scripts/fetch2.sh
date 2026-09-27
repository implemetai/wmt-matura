#!/bin/bash
cd /workspace/maly/models
MR=mradermacher/Bielik-4.5B-v3-Istruct-ungated-i1-GGUF
for q in IQ4_XS Q3_K_L Q4_K_S; do
  f=Bielik-4.5B-v3-Istruct-ungated.i1-$q.gguf
  [ -s "$f" ] || hf download $MR $f --local-dir . >> /scratch/maly/logs/fetch2.log 2>&1
done
sha256sum *.gguf > SHA256SUMS
echo FETCH2_DONE >> /scratch/maly/logs/fetch2.log
