"""Essay RFT, step 3: rule-based selection (no LLM judge) of the sampled essays and the SFT rows built from them.

Every essay (gen_essays.py record + its harness call log, ESSAY_LOG_CALLS) is checked with
  - the ESSAY_SAFE strict checker (cke_essay.count_unsupported over the essay's own passages): 0 unsupported claims
  - 550 <= words <= 850 (cke_essay.body_words)
  - a stance in the introduction (cke_essay._STANCE_RE) and a conclusion that restates it (stance / thesis words)
  - every required element (the topic's aspects, or the planned rulers / events for 'trzech wybranych ...' frames)
    mentioned in its own body paragraph (a perfect element -> paragraph matching)
  - no bullet / numbered lists, no copied prompt text (the topic frame, instruction words, sentences whose word
    trigrams are >= 60% the topic's -- stance sentences excepted), no fallback (v2 essay) path
Per topic the best passing essay is kept (the largest share of the model's own generated text left after the
harness clean-up / verification / trimming to 650 words, then words closest to 650); none when no essay passes. Training rows = that essay's logged calls tagged intro / body* / compare / end: [system, user] -> the
paragraph exactly as handed in (after the harness clean-up and verification; removed sentences stay removed).
The intro row is dropped when the harness had to add its template stance sentence (not the model's own text).

    python train/essay_rft/select_rft.py --essays out/essays.jsonl --calls out/calls.jsonl --out out/rft_rows.jsonl
"""
from __future__ import annotations

import argparse
import collections
import difflib
import itertools
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from harness import cke_essay  # noqa: E402
from harness import essay as essay_mod  # noqa: E402
from harness.essay import _SENT, word_count  # noqa: E402
from harness.qtype import essay_aspects  # noqa: E402

TRAIN_TAGS = re.compile(r"^(intro|body\d+|compare|end)$")
HEADER = re.compile(r"^\s*WYPRACOWANIE na temat nr \S+\s*")
BULLET = re.compile(r"^\s*([-*•–]|\d{1,2}[.)]|[a-e]\))\s+", re.M)
ECHO = re.compile(r"\bakapit\w*|stanowisko\s+autora|wstęp\w*\s+do\s+wypracowania|\bwe\s+fragmentach\b|"
                  r"powyższ\w*\s+fragment\w*|podanych\s+fragment\w*|\btemat\s+nr\b|zajmij\s+stanowisko|"
                  r"uwzględniając\s+w\s+swojej\s+argumentacji|powyższej\s+tezy|napisz\s", re.I)
END_STANCE = re.compile(r"\btez[aęyie]\b|stanowisk|zgadzam|słuszn|trafn|potwierdz|uzasadni|dowodz|świadcz|rzeczywiście|"
                        r"istotnie|niewątpliwie|bez\s+wątpienia|należy\s+(uznać|stwierdzić)|można\s+(zatem\s+)?"
                        r"(stwierdzić|uznać)", re.I)
STOP = {"oraz", "który", "która", "które", "jego", "jej", "ich", "przez", "dla", "przy", "nad", "pod", "między",
        "wobec", "roku", "latach", "wieku", "wiek", "okres", "okresie", "czasie", "polityka", "polityki",
        "panowanie", "panowania", "reformy", "reforma", "wojna", "wojny", "sprawa", "aspekt", "aspekcie", "kraju"}


def paragraphs(answer: str) -> list[str]:
    body = HEADER.sub("", (answer or "").replace("\r\n", "\n"))
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n|\n", body) if p.strip()]


def _tri(s: str) -> set:
    w = re.findall(r"\w+", (s or "").lower())
    return {" ".join(w[i:i + 3]) for i in range(len(w) - 2)}


def keys(element: str, is_aspect: bool) -> list[str]:
    """Stems that show a paragraph talks about the element ('militarny' -> 'militar'; 'Kazimierz Wielki' ->
    'kazim', 'wielk'; 'bitwa pod Grunwaldem' -> 'grunw')."""
    words = re.findall(r"[\wąćęłńóśźż]+", element.lower())
    if is_aspect:
        return [w[:max(5, len(w) - 3)] for w in re.split(r"[-\s]+", element.lower()) if len(w) >= 4] or [element.lower()]
    caps = [w for w in re.findall(r"[A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż]+", element) if len(w) >= 3]
    base = [w.lower() for w in caps] or [w for w in words if len(w) >= 4 and w not in STOP]
    return [w[:5] if len(w) > 5 else w for w in base] or words[:1]


def mentions(par: str, ks: list[str]) -> bool:
    low = par.lower()
    return any(re.search(r"(?<![\wąćęłńóśźż])" + re.escape(k), low) for k in ks)


def elements_ok(bodies: list[str], elements: list[str], is_aspect: bool) -> bool:
    if not elements or len(bodies) < len(elements):
        return False
    ks = [keys(e, is_aspect) for e in elements]
    ok = [[mentions(b, k) for b in bodies] for k in ks]
    return any(all(ok[i][j] for i, j in enumerate(perm))
               for perm in itertools.permutations(range(len(bodies)), len(elements)))


def check(rec: dict, parts: dict) -> tuple[dict, list[str]]:
    """-> (stats, failed checks)."""
    ans = rec.get("answer") or ""
    topic = parts["topic_text"]
    fr = tuple(parts["frame"]) if parts.get("frame") else None
    pars = paragraphs(ans)
    fails = []
    words = cke_essay.body_words(ans)
    if not 550 <= words <= 850:
        fails.append("words")
    aud = cke_essay.count_unsupported(ans, parts["passages"], fr)
    if aud["unsupported"]:
        fails.append("unsupported")
    if len(pars) < 4:
        fails.append("paragraphs")
    intro, end, bodies = (pars[0], pars[-1], pars[1:-1]) if len(pars) >= 3 else ("", "", [])
    if not cke_essay._STANCE_RE.search(intro):
        fails.append("stance_intro")
    thesis = essay_mod.plan("1", topic, topic).thesis
    tk = {w[:5] for w in re.findall(r"[\wąćęłńóśźż]{5,}", thesis.lower())}
    ek = {w[:5] for w in re.findall(r"[\wąćęłńóśźż]{5,}", end.lower())}
    if not END_STANCE.search(end) and not (tk and len(tk & ek) >= 0.5 * len(tk)):  # stance words / thesis restated
        fails.append("stance_end")
    aspects = essay_aspects(topic)
    elements = parts.get("elements") or []
    _, _, n_el = cke_essay.element_kind(topic)
    need = aspects or elements
    if not aspects and len(elements) < min(n_el, 3):
        fails.append("elements_planned")
    if not elements_ok(bodies, need, bool(aspects)):
        fails.append("elements_paragraphs")
    if BULLET.search(HEADER.sub("", ans)):
        fails.append("bullets")
    tt = _tri(topic)
    copied = 0
    for p in pars:
        for x in _SENT.split(p):
            g = _tri(x)
            if ECHO.search(x) or (len(g) >= 4 and len(g & tt) >= 0.6 * len(g) and not cke_essay._STANCE_RE.search(x)):
                copied += 1
    if copied:
        fails.append("prompt_copy")
    e = rec.get("essay") or {}
    if rec.get("mode") != "cke-essay" or e.get("fallback_v2") or any(c.get("fallback_v2") for c in
                                                                      (e.get("safe") or {}).get("candidates", [])):
        fails.append("fallback")
    edits = int(e.get("n_removed") or 0) + len(e.get("verify") or []) + len(e.get("verify_intro_end") or [])
    return {"words": words, "unsupported": aud["unsupported"], "paragraphs": len(pars), "edits": edits,
            "stance_added": bool(e.get("stance_added"))}, fails


def rows_for(rec: dict, parts: dict, calls: dict) -> tuple[list[dict], list[str]]:
    """SFT rows for the kept essay: logged messages (without the assistant prefill) -> paragraph as handed in."""
    final = paragraphs(rec["answer"])
    ptexts = [" ".join(p["text"].split()) for p in parts["parts"]]
    tags = [p["tag"] for p in parts["parts"]]
    if len(final) == len(ptexts):
        pairs = list(zip(tags, final))
    else:  # essay.clean dropped / merged a paragraph: match each logged part to its closest final paragraph
        pairs = []
        for t, pt in zip(tags, ptexts):
            best = max(final, key=lambda f: difflib.SequenceMatcher(None, pt, f).quick_ratio())
            pairs.append((t, best))
    out, skipped = [], []
    for (t, target), pt in zip(pairs, ptexts):
        if not TRAIN_TAGS.match(t):
            continue
        if t == "intro" and parts.get("stance_added"):
            skipped.append("intro_stance_added")
            continue
        c = calls.get(t)
        if not c:
            skipped.append(f"{t}_no_call")
            continue
        if difflib.SequenceMatcher(None, pt, target).ratio() < 0.6:
            skipped.append(f"{t}_mismatch")
            continue
        msgs = [m for m in c["messages"] if m.get("role") != "assistant"]
        if not target.strip() or word_count(target) < 15:
            skipped.append(f"{t}_short")
            continue
        out.append({"messages": msgs + [{"role": "assistant", "content": target}],
                    "meta": {"type": "essay_" + re.sub(r"\d+$", "", t), "tag": t, "topic_id": rec["topic_id"],
                             "k": rec["k"], "source": rec["source"], "prefill": c.get("prefill") or "",
                             "completion_raw": c.get("completion"), "finish": c.get("finish_reason"),
                             "edited": " ".join(c.get("completion", "").split()) != target}})
    return out, skipped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--essays", required=True)
    ap.add_argument("--calls", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    recs = [json.loads(ln) for ln in open(args.essays, encoding="utf-8") if ln.strip()]
    recs = [r for r in recs if not r.get("error") and r.get("essay_log_id")]
    by_id: dict = collections.defaultdict(lambda: {"calls": {}, "parts": []})
    for ln in open(args.calls, encoding="utf-8"):
        if not ln.strip():
            continue
        d = json.loads(ln)
        slot = by_id[d["essay_request_id"]]
        if d["kind"] == "call":
            slot["calls"].setdefault(d["tag"], d)  # one call per tag per written essay (single topic)
        elif d["kind"] == "parts":
            slot["parts"].append(d)
    fail_n, per_topic = collections.Counter(), collections.defaultdict(list)
    n_checked = 0
    for r in recs:
        log = by_id.get(r["essay_log_id"])
        if not log or len(log["parts"]) != 1:
            fail_n["no_log_or_multi" if log else "no_log"] += 1
            continue
        n_checked += 1
        st, fails = check(r, log["parts"][0])
        for f in fails:
            fail_n[f] += 1
        if not fails:
            gen_chars = sum(len(" ".join((c.get("completion") or "").split())) for t, c in log["calls"].items()
                            if TRAIN_TAGS.match(t))
            st["own_frac"] = round(sum(len(p) for p in paragraphs(r["answer"])) / max(1, gen_chars), 3)
            per_topic[r["topic_id"]].append((st, r))
    rows, kept, skipped = [], [], collections.Counter()
    for tid, cands in per_topic.items():
        st, r = min(cands, key=lambda x: (-x[0]["own_frac"], abs(x[0]["words"] - 650), x[1]["k"]))
        log = by_id[r["essay_log_id"]]
        rr, sk = rows_for(r, log["parts"][0], log["calls"])
        skipped.update(sk)
        if rr:
            rows += rr
            kept.append({"topic_id": tid, "k": r["k"], "source": r["source"], "n_pass": len(cands), **st,
                         "rows": len(rr)})
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    topics_all = {r["topic_id"] for r in recs}
    stats = {"essays": len(recs), "essays_checked": n_checked, "topics": len(topics_all),
             "essays_passing": sum(len(v) for v in per_topic.values()), "topics_kept": len(kept),
             "topics_kept_by_source": dict(collections.Counter(k["source"] for k in kept)),
             "rows": len(rows), "rows_by_tag": dict(collections.Counter(x["meta"]["type"] for x in rows)),
             "rows_edited": sum(1 for x in rows if x["meta"]["edited"]), "fail_counts": dict(fail_n),
             "rows_skipped": dict(skipped), "kept": kept}
    json.dump(stats, open(args.out + ".stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in stats.items() if k != "kept"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
