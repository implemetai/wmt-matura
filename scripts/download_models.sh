#!/bin/bash
# Download everything the final system needs next to the code and verify sha256:
#   weights (exact files we run, unmodified originals) + the prebuilt Polish-Wikipedia BM25 index.
# They live in the Hugging Face repo zeemowo/vibers-wmt-matura (GitHub cannot hold 5-7 GB files); the original
# upstream repos are the fallback for the weights.
#
#   scripts/download_models.sh [DEST]        # default DEST=models/final (weights) and DEST/kb_index (index)
#
# Then run the final with these paths:
#   BIELIK=DEST/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf VLM_MODEL=DEST/Qwen3.5-9B-Q5_K_M.gguf VLM_MMPROJ=DEST/mmproj-F16.gguf \
#   RERANKER=DEST/bge-reranker-v2-m3-Q8_0.gguf KB_INDEX_DIR=DEST/kb_index LS=/path/to/llama-server \
#   scripts/run_final.sh PKG_DIR
# Needs the `hf` CLI (pip install -U huggingface_hub) or curl.
set -euo pipefail
DEST=${1:-models/final}
REPO=${HF_REPO:-zeemowo/vibers-wmt-matura}
mkdir -p "$DEST/kb_index"

# file | sha256 | upstream repo (fallback) | role
MODELS="
Bielik-4.5B-v3.0-Instruct.Q8_0.gguf|562f2291de257890adf2b4a914da8b194affe6a7a838a6b7ef3d342f306c1b7f|speakleash/Bielik-4.5B-v3.0-Instruct-GGUF|answering model (registered untouched base, 5.06 GB)
Qwen3.5-9B-Q5_K_M.gguf|dc2a39aef291f91a9116ad214058da0d86eb648743a124bd8c333787c4b9c91c|unsloth/Qwen3.5-9B-GGUF|image describer (6.58 GB)
mmproj-F16.gguf|f70dc3509053962b0d0d3ee8a7eacebf5d60aa560cad78254ae8698516ae029f|unsloth/Qwen3.5-9B-GGUF|image describer vision projector (0.92 GB)
bge-reranker-v2-m3-Q8_0.gguf|a43c7c9b11a4c1517e5bf95151960e1621d1b72f7a493364b01e386cf1aaa1d3|gpustack/bge-reranker-v2-m3-GGUF|retrieval reranker (0.64 GB)
"

fetch() {  # $1 repo, $2 path in repo, $3 local dir
  if command -v hf >/dev/null 2>&1; then
    hf download "$1" "$2" --local-dir "$3" >/dev/null
  else
    mkdir -p "$3/$(dirname "$2")"
    curl -fL --retry 3 -o "$3/$2" "https://huggingface.co/$1/resolve/main/$2"
  fi
}

echo "$MODELS" | while IFS='|' read -r file sha upstream role; do
  [ -z "$file" ] && continue
  if [ -f "$DEST/$file" ] && echo "$sha  $DEST/$file" | sha256sum -c --status; then echo "ok (cached)  $file"; continue; fi
  echo "downloading  $file — $role"
  fetch "$REPO" "$file" "$DEST" || fetch "$upstream" "$file" "$DEST"
  echo "$sha  $DEST/$file" | sha256sum -c --status || { echo "SHA256 MISMATCH: $DEST/$file" >&2; exit 1; }
  echo "ok           $file"
done

echo "downloading  kb_index/ (Polish Wikipedia BM25 index, 5.4 GB, CC BY-SA 4.0)"
if command -v hf >/dev/null 2>&1; then
  hf download "$REPO" --include "kb_index/*" --local-dir "$DEST" >/dev/null
else
  fetch "$REPO" kb_index/SHA256SUMS "$DEST"
  awk '{print $2}' "$DEST/kb_index/SHA256SUMS" | while read -r f; do fetch "$REPO" "kb_index/$f" "$DEST"; done
fi
(cd "$DEST/kb_index" && sha256sum -c --quiet SHA256SUMS) || { echo "kb_index checksum mismatch" >&2; exit 1; }
echo "all files in $DEST verified (weights + kb_index)"
