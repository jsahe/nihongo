#!/usr/bin/env python3
"""Check a week file before committing:  python3 tools/check_week.py weeks/week-01.json

Errors (exit 1): structure the app rejects, kanji outside furigana markup, typed answers with kanji,
dictation answers that don't match their audio, order items whose words don't rebuild the answer,
fill-in prompts that already contain the answer, passages with more than 5 kanji beyond the base set.
Warnings: multiple-choice answers bunched in one position, pitch that disagrees with data/vocab.json.
(Added Nov 17, 2026 after the Week 0 notes: answers were always option 1 or 3, and labels gave blanks away.)
"""
import json, re, sys, os, unicodedata
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FURI = re.compile(r"\{([^{}|]+)\|([^{}]+)\}")
KANJI = re.compile(r"[㐀-鿿々]")
def kana_of(t): return FURI.sub(r"\2", t or "")
def strip_markup(t): return FURI.sub("", t or "")
def hira(s): return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)
def jnorm(s): return re.sub(r"[\s、。，．,.!?！？「」『』（）()・~～〜…]", "", hira(unicodedata.normalize("NFKC", s or ""))).lower()

def main(path):
    w = json.load(open(path, encoding="utf-8"))
    kdb = json.load(open(os.path.join(ROOT, "data", "kanji.json"), encoding="utf-8"))
    vocab = json.load(open(os.path.join(ROOT, "data", "vocab.json"), encoding="utf-8"))
    vp = {(e["w"], e["r"]): e.get("p") for e in vocab}
    base = {k for k, v in kdb.items() if v.get("l") in (5, 4) or v.get("g")}
    week_k = {c["kanji"] for c in w.get("cards", []) if c.get("type") == "write"}
    err, warn = [], []
    def bare_kanji(where, t):
        if t and KANJI.search(strip_markup(t)): err.append("%s: kanji outside {漢字|かな} markup: %s" % (where, strip_markup(t)[:60]))
    # cards
    ids = set()
    for c in w.get("cards", []):
        if c["id"] in ids: err.append("duplicate card id " + c["id"])
        ids.add(c["id"])
        if c.get("type") == "write" and c.get("kanji", "?") not in c["de"]: err.append(c["id"] + ": kanji not in de")
        if "{" in c["de"]: err.append(c["id"] + ": de must be plain text")
        if c.get("example"): bare_kanji(c["id"] + " example", c["example"])
        p = vp.get((c["de"], c["reading"]))
        if p is not None and c.get("pitch") is not None and p != c["pitch"]: warn.append("%s: pitch %s, vocab.json says %s" % (c["id"], c["pitch"], p))
    per_day = Counter((c["day"], c.get("type", "read")) for c in w.get("cards", []))
    # days
    eids, mc = set(), []
    for d in w["days"]:
        bare_kanji("day %d title" % d["day"], d.get("title"))
        for s in d["sections"]:
            t = s["type"]
            if t == "reading":
                bare_kanji("day %d reading" % d["day"], s["text"])
                new = sorted({k for k in KANJI.findall(s["text"]) if k not in base and k not in week_k and k != "々"})
                if len(new) > 5: err.append("day %d reading: %d kanji beyond the base set (max 5): %s" % (d["day"], len(new), "".join(new)))
            if t == "grammar":
                for e in s.get("examples", []): bare_kanji("day %d grammar example" % d["day"], e)
            if t == "exercises":
                for it in s["items"]:
                    i = it["id"]
                    if i in eids: err.append("duplicate exercise id " + i)
                    eids.add(i); k = it["kind"]
                    for f in ("prompt", "modelAnswer", "audio", "answer" if k == "order" else None):
                        if f and isinstance(it.get(f), str): bare_kanji(i + " " + f, it[f])
                    for o in it.get("options", []): bare_kanji(i + " option", o)
                    if k == "multiple_choice": mc.append(it["answer"])
                    if k == "fill_blank":
                        pk = jnorm(kana_of(it["prompt"]))
                        for alts in it["answers"]:
                            for a in alts:
                                if KANJI.search(a): err.append(i + ": typed answer has kanji: " + a)
                                if len(jnorm(a)) >= 2 and jnorm(a) in pk: err.append(i + ": the prompt already contains the answer \"%s\"" % a)
                    if k in ("translate",) and it.get("direction", "en-ja") == "en-ja":
                        for a in it.get("acceptable", []):
                            if KANJI.search(a): err.append(i + ": acceptable answer has kanji: " + a)
                    if k == "dictation":
                        want = jnorm(kana_of(it["audio"]))
                        if not any(jnorm(a) == want for a in it["answers"]): err.append("%s: no answer matches the audio's kana (%s)" % (i, want))
                    if k == "order":
                        if re.sub(r"\s", "", "".join(it["words"])) != re.sub(r"\s", "", it["answer"]): err.append(i + ": words don't rebuild the answer")
                    if k == "match":
                        for a, b in it["pairs"]: bare_kanji(i + " pair", a)
    for x in (w.get("extras") or {}).get("readings", []):
        bare_kanji(x["id"], x["text"])
        new = sorted({k for k in KANJI.findall(x["text"]) if k not in base and k not in week_k and k != "々"})
        if len(new) > 5: err.append("%s: %d kanji beyond the base set (max 5): %s" % (x["id"], len(new), "".join(new)))
        for q in x.get("questions", []):
            bare_kanji(x["id"] + " q", q["q"]); [bare_kanji(x["id"] + " opt", o) for o in q["options"]]
    for x in (w.get("extras") or {}).get("dictations", []):
        bare_kanji(x["id"], x["audio"])
        if not any(jnorm(a) == jnorm(kana_of(x["audio"])) for a in x["answers"]): err.append(x["id"] + ": answer doesn't match audio")
    if len(mc) >= 6:
        c = Counter(mc); top, n = c.most_common(1)[0]
        if n / len(mc) > 0.4: warn.append("multiple choice: answer index %d in %d of %d items; spread them out" % (top, n, len(mc)))
        if len(c) < min(4, max(mc) + 1): warn.append("multiple choice: positions used %s" % dict(c))
    print("cards per day:", ", ".join("D%d %dr+%dw" % (d, per_day[(d, "read")], per_day[(d, "write")]) for d in range(1, 8)))
    print("MC answer positions:", dict(Counter(mc)))
    for x in warn: print("WARN", x)
    for x in err: print("ERROR", x)
    print("ok" if not err else "%d errors" % len(err))
    return 1 if err else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
