"""Essay RFT, step 6: the 12 formula-2023 essays (devset/cke-essays.jsonl, evaluation only) exactly as
harness/exam_runner.py --mode hybrid sends item 26 (POST /answer {"question": text, "id": "26", "system": essay
format instruction}, then post_format), one request at a time, with the essay adapter served at scale 0 by default
and sent at scale 1 by the harness for essay-flow calls only (CKE_LORA_TYPES=essay CKE_LORA_SCALE=1).

Before and after the essays it checks the LoRA routing on the same llama-server: a raw request (as exam_runner raw
mode sends it, T=0) without a 'lora' field must equal the one with every adapter at scale 0 (server default 0) and
differ from scale 1; GET /lora-adapters must still show scale 0 after the essays.

    python train/essay_rft/eval_rft.py --llm http://127.0.0.1:18330 --harness http://127.0.0.1:18333 \
        --out /scratch/essay_rft/out/answers_rft.jsonl --system rft
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from harness.exam_runner import _get, _post, essay_words, format_instruction, post_format, spec_for  # noqa: E402

PROBE = ("Który władca zwołał pierwszy sejm walny w Piotrkowie w 1493 roku?\n\n"
         "Odpowiedź po polsku, bez toku rozumowania. Podaj imię i przydomek władcy.")


def raw(llm: str, lora: list | None) -> str:
    body = {"model": "bielik-4.5b-v3", "messages": [{"role": "user", "content": PROBE}], "temperature": 0,
            "max_tokens": 80, "cache_prompt": True}
    if lora is not None:
        body["lora"] = lora
    d = _post(llm.rstrip("/") + "/v1/chat/completions", body, 300)
    return ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


def lora_check(llm: str) -> dict:
    ads = _get(llm.rstrip("/") + "/lora-adapters")
    ids = [a["id"] for a in ads] if isinstance(ads, list) else []
    a = raw(llm, None)
    z = raw(llm, [{"id": i, "scale": 0.0} for i in ids])
    o = raw(llm, [{"id": i, "scale": 1.0} for i in ids])
    a2 = raw(llm, None)
    return {"adapters": ads, "default_eq_zero": a == z, "default_stable": a == a2, "scale1_differs": o != a,
            "default": a[:160], "scale1": o[:160]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", required=True)
    ap.add_argument("--harness", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--system", default="rft")
    args = ap.parse_args()
    mock = json.load(open(os.path.join(ROOT, "data_cke/mock2023/exam.json"), encoding="utf-8"))
    essay_af = {it["id"]: it["answer_format"] for it in mock["items"]}["26"]
    rows = [json.loads(ln) for ln in open(os.path.join(ROOT, "devset/cke-essays.jsonl"), encoding="utf-8")
            if ln.strip()]
    rows = [r for r in rows if r.get("formula") == "2023"]
    assert len(rows) == 12, len(rows)
    pre = lora_check(args.llm)
    print("lora check (before):", json.dumps(pre, ensure_ascii=False)[:600], flush=True)
    out = []
    for r in rows:
        text = r["question"].replace("\r\n", "\n").strip()
        item = {"id": "26", "question": text, "source_text": "", "images": [], "answer_format": essay_af}
        hint = format_instruction(item, spec_for(item))
        t0 = time.time()
        row = {"id": r["id"], "system": args.system}
        try:
            d = _post(args.harness.rstrip("/") + "/answer", {"question": text, "id": "26", "system": hint}, 1800)
            ess = (d.get("parsed") or {}).get("essay") or {}
            final, ok, note = post_format(item, d.get("answer") or "")
            row.update({"answer": final, "words": essay_words(final), "latency": round(time.time() - t0, 1),
                        "format_ok": ok, "note": note, "qtype": d.get("qtype"), "mode": d.get("mode"),
                        "llm_calls": d.get("llm_calls"), "lora_off": ess.get("lora_off"),
                        "essay_meta": {k: ess.get(k) for k in ("topic", "words", "unsupported", "unsupported_parts",
                                                                "n_removed", "frame", "stance_added") if k in ess},
                        "meta": {"topic": ess.get("topic"), "unsupported": ess.get("unsupported"),
                                 "safe": ess.get("safe")}})
        except Exception as e:  # noqa: BLE001
            row.update({"answer": "", "words": 0, "latency": round(time.time() - t0, 1),
                        "error": f"{type(e).__name__}: {e}"[:300]})
        out.append(row)
        print(f"{time.strftime('%H:%M:%S')} {r['id']:34s} {row['latency']:6.1f}s {row['words']:4d} words "
              f"topic {row.get('meta', {}).get('topic')} unsup {row.get('meta', {}).get('unsupported')} "
              f"{row.get('error') or ''}", flush=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            for x in out:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    post = lora_check(args.llm)
    print("lora check (after):", json.dumps(post, ensure_ascii=False)[:600], flush=True)
    json.dump({"before": pre, "after": post}, open(args.out + ".lora_check.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    ok = [x for x in out if not x.get("error")]
    lat = [x["latency"] for x in ok]
    w = [x["words"] for x in ok]
    print(f"EVAL_DONE {len(ok)}/12 ok, latency mean {sum(lat) / max(1, len(lat)):.1f}s max {max(lat or [0]):.1f}s, "
          f"words mean {sum(w) / max(1, len(w)):.0f} min {min(w or [0])} max {max(w or [0])}", flush=True)


if __name__ == "__main__":
    main()
