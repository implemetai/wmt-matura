#!/bin/bash
# Check how llama-server b11185 applies an adapter loaded for the essay only: raw requests (as exam_runner raw mode
# sends them, T=0) against (a) the untouched base server without adapter and (b) the server with the adapter after
# --lora-init-without-apply, after a global POST /lora-adapters scale 0, with per-request 'lora' scale 0 / 1.
#   ADAPTER=/scratch/essay_rft/loras/x.gguf bash train/essay_rft/lora_default_test.sh
set -u
LS=/scratch/ovl/opt/llama/current/llama-server
BIELIK=/scratch/ovl/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf
PY=/scratch/ovl/venvs/wmt/bin/python
ADAPTER=${ADAPTER:?set ADAPTER}
O=/scratch/essay_rft/out
P=18330
PID=""
cleanup() { [ -n "$PID" ] && kill $PID 2>/dev/null; sleep 2; [ -n "$PID" ] && kill -9 $PID 2>/dev/null; }
trap cleanup EXIT
up() { for i in $(seq 1 300); do curl -sf http://127.0.0.1:$P/health >/dev/null 2>&1 && return 0; sleep 1; done; return 1; }
curl -s -m 2 http://127.0.0.1:$P/health >/dev/null 2>&1 && { echo "port $P busy"; exit 1; }
probe() {  # $1 = label, $2 = extra JSON fields (e.g. ',"lora":[...]')
  $PY - "$1" "$2" <<'EOF'
import json, sys, urllib.request
qs = ["Który władca zwołał pierwszy sejm walny w Piotrkowie w 1493 roku?\n\nOdpowiedź po polsku, bez toku rozumowania.",
      "Wyjaśnij, jakie znaczenie dla Rzeczypospolitej miała unia lubelska z 1569 roku.\n\nOdpowiedź po polsku, bez toku rozumowania. Tekst po polsku. Podaj wszystkie wymagane elementy odpowiedzi."]
out = []
for q in qs:
    body = {"model": "bielik-4.5b-v3", "messages": [{"role": "user", "content": q}], "temperature": 0,
            "max_tokens": 120, "cache_prompt": True}
    body.update(json.loads("{" + sys.argv[2].lstrip(",") + "}") if sys.argv[2] else {})
    req = urllib.request.Request("http://127.0.0.1:18330/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    out.append(json.loads(urllib.request.urlopen(req, timeout=300).read())["choices"][0]["message"]["content"])
print(json.dumps({"label": sys.argv[1], "out": out}, ensure_ascii=False))
EOF
}
R=$O/lora_default_test.jsonl; : > $R
"$LS" -m "$BIELIK" --host 127.0.0.1 --port $P -ngl 999 -c 8192 -np 1 -fa on --jinja --cache-ram 0 --no-webui \
  > $O/lora_test_base.log 2>&1 < /dev/null & PID=$!
up || { tail $O/lora_test_base.log; exit 1; }
probe base "" >> $R
cleanup; PID=""
"$LS" -m "$BIELIK" --lora "$ADAPTER" --lora-init-without-apply --host 127.0.0.1 --port $P -ngl 999 -c 8192 -np 1 \
  -fa on --jinja --cache-ram 0 --no-webui > $O/lora_test_ad.log 2>&1 < /dev/null & PID=$!
up || { tail $O/lora_test_ad.log; exit 1; }
echo "adapters at start: $(curl -s http://127.0.0.1:$P/lora-adapters)"
probe init_default "" >> $R
probe req_scale1 ',"lora":[{"id":0,"scale":1.0}]' >> $R
probe req_scale0 ',"lora":[{"id":0,"scale":0.0}]' >> $R
curl -s -X POST http://127.0.0.1:$P/lora-adapters -H 'Content-Type: application/json' -d '[{"id":0,"scale":0.0}]' >/dev/null
echo "adapters after POST 0: $(curl -s http://127.0.0.1:$P/lora-adapters)"
probe global0_default "" >> $R
probe global0_req_scale1 ',"lora":[{"id":0,"scale":1.0}]' >> $R
probe global0_default_again "" >> $R
$PY - $R <<'EOF'
import json, sys
d = {x["label"]: x["out"] for x in map(json.loads, open(sys.argv[1]))}
b = d["base"]
for k, v in d.items():
    print(f"{k:24s} == base: {v == b}   == req_scale1: {v == d['req_scale1']}")
EOF
echo LORA_TEST_DONE
