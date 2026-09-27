#!/bin/bash
# eval2.sh PORT TAG=GGUF ...  -- like eval.sh, but work dir on local /scratch (network FS had a write outage),
# skips parts already complete, fails fast if the server does not come up, then copies results to /workspace.
set -u
PORT=$1; shift
R=/scratch/maly/code; PY=/scratch/mock/wmt-matura/.venv/bin/python; LS=/scratch/ovl/opt/llama/current/llama-server
W=/scratch/maly/runs; LOG=/scratch/maly/logs; DST=/workspace/maly/runs
cd $R
complete() {  # $1 file, $2 expected ok rows
  $PY -c "import json,sys;r=[json.loads(l) for l in open(sys.argv[1],encoding='utf-8') if l.strip()];sys.exit(0 if sum(1 for x in r if x.get('answer') and not x.get('error'))>=int(sys.argv[2]) else 1)" "$1" "$2" 2>/dev/null
}
mock_complete() { $PY -c "import json,sys;a=json.load(open(sys.argv[1],encoding='utf-8'))['answers'];sys.exit(0 if sum(1 for x in a if x['answer'].strip())==37 else 1)" "$1" 2>/dev/null; }
for spec in "$@"; do
  TAG=${spec%%=*}; GGUF=${spec#*=}
  mkdir -p $W/$TAG/mock
  [ -d $DST/$TAG ] && false && cp -rn $DST/$TAG/. $W/$TAG/ 2>/dev/null
  nohup $LS -m $GGUF --host 127.0.0.1 --port $PORT -ngl 999 -c 16384 -np 1 -fa on --jinja \
    --alias $TAG --cache-ram 0 --no-webui > $LOG/llama-$TAG.log 2>&1 < /dev/null &
  LPID=$!; up=0
  for i in $(seq 1 180); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && { up=1; break; }; kill -0 $LPID 2>/dev/null || break; sleep 1; done
  if [ $up = 0 ]; then echo "$(date +%T) $TAG SERVER FAILED"; kill $LPID 2>/dev/null; continue; fi
  echo "$(date +%T) $TAG server up"
  if ! mock_complete $W/$TAG/mock/answers.json; then
    rm -f $W/$TAG/mock/*
    $PY -m harness.exam_runner data_cke/mock2023/exam.json --mode raw --llm-url http://127.0.0.1:$PORT \
      --model $TAG --concurrency 1 --system-name maly-$TAG --out $W/$TAG/mock/answers.json > $LOG/mock-$TAG.log 2>&1
    echo "$(date +%T) $TAG mock rc=$?"
  fi
  for pn in cke2024:30 cke2025:24 cke2026:25; do
    p=${pn%%:*}; n=${pn#*:}
    complete $W/$TAG/$p.jsonl $n && continue
    rm -f $W/$TAG/$p.jsonl
    $PY devset/cke_full/run_paper.py devset/cke_full/$p.jsonl $W/$TAG/$p.jsonl --mode raw \
      --url http://127.0.0.1:$PORT --conc 1 --system $TAG > $LOG/paper-$TAG-$p.log 2>&1
    echo "$(date +%T) $TAG $p rc=$?"
  done
  kill $LPID; wait $LPID 2>/dev/null
  date +%T > $W/$TAG/DONE; mkdir -p $DST/$TAG 2>/dev/null && cp -r $W/$TAG/. $DST/$TAG/ 2>/dev/null
  echo "$(date +%T) $TAG done"
done
echo LANE_DONE
