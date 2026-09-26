"""Extract single essay topics from OLD-formula CKE papers (2003-2022).

Reads git-ignored CKE files; never touches the formula-2023 rows (eval set).
Output rows: {id, source:'cke_old', topic, paper, needs_materials}.
"""
import glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVAL_IDS = {  # formula-2023 essay rows = evaluation set, never used
    'cke-essay-2022-grudzien-probna', 'cke-essay-2023-czerwiec', 'cke-essay-2023-maj',
    'cke-essay-2023-przykladowy', 'cke-essay-2024-czerwiec', 'cke-essay-2024-grudzien-probna',
    'cke-essay-2024-maj', 'cke-essay-2025-czerwiec', 'cke-essay-2025-maj',
    'cke-essay-2026-czerwiec', 'cke-essay-2026-maj', 'cke-essay-2026-styczen-probna'}
MAT_RE = re.compile(r'\s*W pracy (?:wykorzystaj materiały źródłowe|odwołaj się do materiałów źródłowych)\s*\([^)]*\)\.?')
CUT_RE = re.compile(r'Poniższy tekst może stanowić inspirację|Wybieram temat|Materiały źródłowe')
ROMAN = {'I': 1, 'II': 2, 'III': 3}


def clean(t):
    t = re.sub(r'(?m)^\s*\*.*$', '', t)            # footnote lines "* W. Broniewski ..."
    t = re.sub(r'\s+1\s+Cyt\. za:.*$', '', t, flags=re.S)  # trailing footnote
    t = re.sub(r'(?<=[a-ząćęłńóśźż])1(?=\.)', '', t)  # footnote marker "Sokolnicki1."
    t = t.replace('giną*', 'giną')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def finish(t):
    needs = bool(MAT_RE.search(t))
    t = MAT_RE.sub('', t).strip()
    return clean(t), needs


def from_devset():
    out = []
    for line in open(os.path.join(ROOT, 'devset', 'cke-essays.jsonl'), encoding='utf-8'):
        r = json.loads(line)
        if r['id'] in EVAL_IDS or r.get('formula') == '2023':
            continue
        if r['id'] == 'cke-essay-2015-maj':
            continue  # same paper as cke_full_items 2015 (that copy keeps the quotes)
        paper = r['id'].replace('cke-essay-', '')
        for t in r['topics']:
            topic, needs = finish(t['text'])
            out.append({'id': f'old-{paper}-t{t["n"]}', 'source': 'cke_old', 'topic': topic,
                        'paper': paper, 'needs_materials': needs or bool(t.get('needs_materials'))})
    return out


def from_full_items():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'train', 'datagen', 'cke_full_items', '*.jsonl'))):
        for line in open(f, encoding='utf-8'):
            r = json.loads(line)
            if r.get('type') != 'essay':
                continue
            m = re.search(r'(\d{4})-(maj|czerwiec)', r['id'])
            paper = f'{m.group(1)}-{m.group(2)}-z{r["task"]}'
            q = r['question']
            parts = re.split(r'(?m)^\s*(?:TEMAT|Temat)\s+(I{1,3})\s*:?\s*', q)
            if len(parts) > 1:
                segs = [(ROMAN[parts[i]], parts[i + 1]) for i in range(1, len(parts), 2)]
            else:
                body = CUT_RE.split(q)[0]
                parts = re.split(r'(?m)^\s*([1-5])\.\s+', body)
                segs = [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts), 2)]
            for n, seg in segs:
                seg = CUT_RE.split(seg)[0]
                topic, needs = finish(seg)
                out.append({'id': f'old-{paper}-t{n}', 'source': 'cke_old', 'topic': topic,
                            'paper': paper, 'needs_materials': needs})
    return out


def load():
    rows = from_full_items() + from_devset()
    seen, uniq = set(), []
    for r in rows:
        k = re.sub(r'[^a-ząćęłńóśźż]', '', r['topic'].lower())
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq


if __name__ == '__main__':
    for r in load():
        print(r['id'], '|', r['needs_materials'], '|', r['topic'])
