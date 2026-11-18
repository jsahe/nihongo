#!/usr/bin/env python3
"""Build the app's static data from open sources.

Inputs (in --src):
  kanji.json            davidluzgouveia/kanji-data (MIT; derived from KANJIDIC2 + JLPT lists)
  accents.txt           mifunetoshiro/kanjium (CC BY-SA 4.0) pitch accents
  n5.csv … n2.csv       jamsinclair/open-anki-jlpt-decks (MIT; vocabulary from Tanos JLPT lists, CC BY)
  kvg/kanji/*.svg       KanjiVG (CC BY-SA 3.0) stroke data
Outputs (in the repo):
  data/kanji.json       N5–N2 kanji (+ Genki extras): level, meanings, readings, key word, components
  data/vocab.json       N5–N2 vocabulary with pitch accent
  strokes/<hex>.json    per-kanji strokes: SVG path + 16 sampled points per stroke (109×109 box)
"""
import argparse, csv, json, os, re, sys
from svgpathtools import parse_path
sys.path.insert(0, os.path.dirname(__file__))
from genki_kanji import GENKI

LEVEL_FIX = {"分": 5}  # source data lists 分 without a JLPT level
KANJI_RE = re.compile(r"[㐀-鿿々]")
def is_kanji(ch): return bool(KANJI_RE.match(ch))

def load_pitch(path):
    by_pair, by_word = {}, {}
    for line in open(path, encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) < 3: continue
        w, r, a = p[0], p[1], p[2].split(",")[0]
        a = re.sub(r"\D", "", a.translate(str.maketrans("０１２３４５６７８９", "0123456789")))
        if a == "": continue
        by_pair.setdefault((w, r), int(a)); by_word.setdefault(w, (r, int(a)))
    return by_pair, by_word

PAREN_RE = re.compile(r"\s*[(（][^)）]*[)）]\s*")
def clean_entry(w, r):
    """Readings are what the learner types, so they must be the bare word:
    'べんきょう (する)' / 'うんどうする' → 'べんきょう'/'うんどう'; '(を) とお' → 'とお'; 'パート (タイム)' → 'パート'."""
    w2 = PAREN_RE.sub("", w).strip() or w.strip()
    r2 = PAREN_RE.sub("", r).strip() or r.strip()
    if "する" not in w2 and r2.endswith("する") and len(r2) > 2 and r2 != w2:
        r2 = r2[:-2]
    return w2, r2

def load_vocab(src, pitch):
    by_pair, by_word = pitch
    out, seen = [], set()
    for lvl in (5, 4, 3, 2):
        for row in csv.DictReader(open(os.path.join(src, "n%d.csv" % lvl), encoding="utf-8")):
            ws = [x.strip() for x in row["expression"].split(";")]
            rs = [x.strip() for x in row["reading"].split(";")]
            w = ws[0].replace("～", "").replace("〜", "")
            r = (rs[0] if len(rs) != len(ws) else rs[0]).replace("～", "").replace("〜", "")
            w, r = clean_entry(w, r)
            if not w or (w, r) in seen: continue
            seen.add((w, r))
            p = by_pair.get((w, r))
            if p is None and w == r: p = by_pair.get((w, r))
            e = {"w": w, "r": r, "m": row["meaning"].strip(), "l": lvl}
            if p is not None: e["p"] = p
            out.append(e)
    return out

def sample(d, n=16):
    path = parse_path(d); L = path.length(error=1e-3)
    pts = []
    for i in range(n):
        t = path.ilength(L * i / (n - 1), error=1e-3) if 0 < i < n - 1 else (0 if i == 0 else 1)
        z = path.point(t); pts.append([round(z.real, 1), round(z.imag, 1)])
    return pts, round(L, 1)

def strokes_for(svg):
    paths = re.findall(r'<path[^>]*\sd="([^"]+)"', svg)
    return paths

def components(svg, k):
    # direct children groups of the main kanji group with an element attribute
    m = re.search(r'<g id="kvg:StrokePaths_[0-9a-f]+"[^>]*>\s*<g id="kvg:[0-9a-f]+"[^>]*>(.*)</g>\s*</g>', svg, re.S)
    if not m: return []
    body = m.group(1); depth = 0; comps = []
    for tok in re.finditer(r'<g\b([^>]*)>|</g>', body):
        if tok.group(0) == "</g>": depth -= 1; continue
        if depth == 0:
            el = re.search(r'kvg:element="([^"]+)"', tok.group(1))
            if el and el.group(1) != k: comps.append(el.group(1))
        depth += 1
    return comps

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True); a = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kd = json.load(open(os.path.join(a.src, "kanji.json"), encoding="utf-8"))
    pitch = load_pitch(os.path.join(a.src, "accents.txt"))
    vocab = load_vocab(a.src, pitch)
    genki = {}
    for lesson, s in GENKI.items():
        for ch in s: genki.setdefault(ch, lesson)
    want = [k for k, v in kd.items() if v.get("jlpt_new") in (5, 4, 3, 2)]
    want += [k for k in genki if k not in want and k in kd]
    out = {}; missing = []
    os.makedirs(os.path.join(root, "strokes"), exist_ok=True)
    for k in want:
        v = kd[k]
        # key word: lowest-level vocab containing k whose other kanji are no harder than k
        lvl = v.get("jlpt_new") or 1
        def ok(e):
            return k in e["w"] and all((kd.get(c, {}).get("jlpt_new") or 0) >= lvl for c in e["w"] if is_kanji(c) and c != k)
        cands = [e for e in vocab if ok(e)] or [e for e in vocab if k in e["w"]]
        cands.sort(key=lambda e: (-e["l"], len(e["w"]) if len(e["w"]) > 1 else 9, len(e["w"])))
        kw = cands[0] if cands else None
        svgp = os.path.join(a.src, "kvg", "kanji", "%05x.svg" % ord(k))
        comps = []
        if os.path.exists(svgp):
            svg = open(svgp, encoding="utf-8").read()
            ds = strokes_for(svg); comps = components(svg, k)
            st = []
            for d in ds:
                pts, L = sample(d); st.append({"d": d, "p": pts, "l": L})
            json.dump({"k": k, "s": st}, open(os.path.join(root, "strokes", "%05x.json" % ord(k)), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        else:
            missing.append(k)
        e = {"l": v.get("jlpt_new") or 0, "m": [x for x in v.get("meanings", []) if "Radical" not in x][:3],
             "on": v.get("readings_on", [])[:3], "kun": v.get("readings_kun", [])[:3], "s": v.get("strokes"), "f": v.get("freq")}
        if k in genki: e["g"] = genki[k]
        if e["l"] in (0, 1) and k in LEVEL_FIX: e["l"] = LEVEL_FIX[k]
        if comps: e["c"] = comps
        if kw: e["kw"] = {x: kw[x] for x in ("w", "r", "m", "p") if x in kw}
        out[k] = e
    json.dump(out, open(os.path.join(root, "data", "kanji.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(vocab, open(os.path.join(root, "data", "vocab.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("kanji", len(out), "genki", len(genki), "vocab", len(vocab), "with pitch", sum(1 for e in vocab if "p" in e), "missing strokes", missing)

if __name__ == "__main__":
    main()
