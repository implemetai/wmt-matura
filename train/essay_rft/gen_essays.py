"""Essay RFT, step 2: sample essays from harness v3 (ESSAY_SAFE=1, ESSAY_LOG_CALLS on) for every topic of
train/essay_rft/topics.jsonl. The harness logs every LLM call of the essay flow; this driver only sends the questions
and keeps the /answer responses (answer, parsed essay meta, essay_log_id) for the rule-based selection.

    python train/essay_rft/gen_essays.py --url http://127.0.0.1:18333 --out /scratch/essay_rft/out/essays.jsonl \
        --n 4 --workers 4 --budget-min 225

Topics marked near_eval (same subject as a formula-2023 evaluation topic) or needs_materials (the old paper's
source materials are not printed) are skipped. Topic order: generated and cke_old interleaved (seeded shuffle), so a
time-limited run still covers both sources. Resumable: (topic id, sample k) pairs already answered are skipped.
The question is the topic text followed by an answer line, so the harness parses exactly one topic (number 1).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import random
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANSWER_LINE = "WYPRACOWANIE na wybrany temat (minimum 300 słów)"


def load_topics(path: str, seed: int = 42) -> list[dict]:
    rows = [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]
    keep = [r for r in rows if not r.get("near_eval") and not r.get("needs_materials")]
    rng = random.Random(seed)
    gen = [r for r in keep if r["source"] == "generated"]
    old = [r for r in keep if r["source"] != "generated"]
    rng.shuffle(gen)
    rng.shuffle(old)
    out, gi, oi = [], 0, 0
    while gi < len(gen) or oi < len(old):  # proportional interleave
        if oi >= len(old) or (gi < len(gen) and gi * len(old) <= oi * len(gen)):
            out.append(gen[gi])
            gi += 1
        else:
            out.append(old[oi])
            oi += 1
    return out


def question(topic: str) -> str:
    return " ".join(topic.split()) + "\n\n" + ANSWER_LINE


def post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", default=os.path.join(ROOT, "train", "essay_rft", "topics.jsonl"))
    ap.add_argument("--url", required=True, help="harness base URL")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=4, help="essays per topic")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--budget-min", type=float, default=225.0, help="no new request after this many minutes")
    ap.add_argument("--limit", type=int, default=0, help="first N topics only (smoke test)")
    ap.add_argument("--timeout", type=float, default=1500.0)
    args = ap.parse_args()
    topics = load_topics(args.topics)
    if args.limit:
        topics = topics[: args.limit]
    done = set()
    if os.path.exists(args.out):
        for ln in open(args.out, encoding="utf-8"):
            if ln.strip():
                d = json.loads(ln)
                if not d.get("error"):
                    done.add((d["topic_id"], d["k"]))
    jobs = [(t, k) for t in topics for k in range(args.n) if (t["id"], k) not in done]
    src = {}
    for t in topics:
        src[t["source"]] = src.get(t["source"], 0) + 1
    print(f"{time.strftime('%H:%M:%S')} topics {len(topics)} {src}, jobs {len(jobs)} (done {len(done)})", flush=True)
    t0 = time.time()
    lock = threading.Lock()
    stats = {"ok": 0, "err": 0, "skipped_budget": 0}

    def work(job):
        t, k = job
        if time.time() - t0 > args.budget_min * 60:
            with lock:
                stats["skipped_budget"] += 1
            return
        rec = {"topic_id": t["id"], "k": k, "source": t["source"], "era": t.get("era"), "topic": t["topic"]}
        t1 = time.time()
        try:
            d = post(args.url.rstrip("/") + "/answer", {"question": question(t["topic"]), "id": f"{t['id']}#{k}"},
                     args.timeout)
            parsed = d.get("parsed") or {}
            rec.update(answer=d.get("answer") or "", qtype=d.get("qtype"), mode=d.get("mode"),
                       essay=parsed.get("essay") or {}, essay_log_id=parsed.get("essay_log_id"),
                       llm_calls=d.get("llm_calls"), completion_tokens=d.get("completion_tokens"))
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
        rec["latency_s"] = round(time.time() - t1, 1)
        with lock:
            stats["err" if rec.get("error") else "ok"] += 1
            with open(args.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n = stats["ok"] + stats["err"]
            if n % 20 == 0 or rec.get("error"):
                el = time.time() - t0
                print(f"{time.strftime('%H:%M:%S')} {n}/{len(jobs)} ok {stats['ok']} err {stats['err']} "
                      f"{el / 60:.1f} min, {el / max(1, n):.1f} s/essay {rec.get('error') or ''}", flush=True)

    with cf.ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(work, jobs))
    print(f"{time.strftime('%H:%M:%S')} GEN_DONE {stats} wall {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
