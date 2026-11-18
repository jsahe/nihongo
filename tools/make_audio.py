#!/usr/bin/env python3
"""Generate mp3 audio for every Japanese text the app can speak, with VOICEVOX.

Usage:  python3 tools/make_audio.py [--only himari,takehiro] [--vv DIR]
First run downloads VOICEVOX CORE 0.16.2 (Python wheel), its ONNX Runtime, the Open JTalk
dictionary and the two voice models from GitHub releases into DIR (default /tmp/voicevox).

Keys must match index.html:
  sentence: clean(kana_of(text))            -> TTS.say(text)
  word:     "w|" + clean(reading) + "|" + pitch -> TTS.word(de, reading, pitch)
  key = FNV-1a 32-bit hash of the UTF-8 bytes (8 hex digits) + "-" + UTF-8 byte length.
Sentences are synthesized from the kanji text (better prosody) unless Open JTalk's reading
disagrees with the furigana in the file; then the kana version is used. Words are synthesized
from kana with the pitch-accent nucleus set explicitly (0 = heiban).
Voices: VOICEVOX:冥鳴ひまり, VOICEVOX:玄野武宏 (credit required; shown in the app).
練習 extras (冥鳴ひまり only): all N5 kanji words, and word+が for nouns (N5 + week cards); manifest in audio/words.json.
"""
import argparse, glob, json, os, re, subprocess, sys, tempfile

VOICES = {"himari": (1, 14), "takehiro": (4, 11)}   # name -> (vvm file, style id)
VV_VERSION = "0.16.2"
URLS = {
    "wheel": f"https://github.com/VOICEVOX/voicevox_core/releases/download/{VV_VERSION}/voicevox_core-{VV_VERSION}-cp310-abi3-manylinux_2_34_x86_64.whl",
    "ort": "https://github.com/VOICEVOX/onnxruntime-builder/releases/download/voicevox_onnxruntime-1.17.3/voicevox_onnxruntime-linux-x64-1.17.3.tgz",
    "dict": "https://github.com/r9y9/open_jtalk/releases/download/v1.11.1/open_jtalk_dic_utf_8-1.11.tar.gz",
    "vvm": "https://github.com/VOICEVOX/voicevox_vvm/releases/download/" + VV_VERSION + "/{n}.vvm",
}
SPEED = 0.92   # slightly slower than default, for learners
FURI = re.compile(r"\{([^{}|]+)\|([^{}]+)\}")
SMALL = "ャュョァィゥェォヮ"

def kana_of(t): return FURI.sub(r"\2", str(t or ""))
def base_of(t): return FURI.sub(r"\1", str(t or ""))
def clean(t):
    t = str(t).replace("**", "")
    t = re.sub(r"^[\s–-]+", "", t, flags=re.M)
    t = re.sub(r"…|\.\.\.", " ", t)
    t = re.sub(r"\([^)]*\)|（[^）]*）", " ", t)
    return re.sub(r"\s+", " ", t).strip()
def key(t):
    b = t.encode("utf-8"); h = 0x811C9DC5
    for x in b: h ^= x; h = (h * 0x01000193) & 0xFFFFFFFF
    return "%08x-%d" % (h, len(b))
def kata(s): return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
def hira(s): return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)

def collect(root):
    words, sents = {}, {}
    def w(de, r, p):
        r = clean(r or "")
        if r: words[key("w|%s|%s" % (r, "" if p is None else p))] = (r, p)
        elif de: s(de)
    def s(t):
        c = clean(kana_of(t))
        if c: sents[key(c)] = t
    for f in sorted(glob.glob(os.path.join(root, "weeks", "week-*.json"))):
        wk = json.load(open(f, encoding="utf-8"))
        for c in wk.get("cards", []):
            w(c.get("de"), c.get("reading"), c.get("pitch")); s(c.get("example", ""))
        for d in wk.get("days", []):
            for sec in d.get("sections", []):
                t = sec.get("type")
                if t == "vocab":
                    for v in sec.get("words", []): w(v.get("de"), (v.get("reading") or "") + v.get("particle", ""), v.get("pitch"))
                if t == "kanji":
                    for v in sec.get("items", []): w(v.get("de"), v.get("reading"), v.get("pitch"))
                if t == "reading": s(sec.get("text", ""))
                if t == "grammar":
                    for e in sec.get("examples", []): s(e)
                if t == "exercises":
                    for it in sec.get("items", []):
                        if it.get("kind") == "dictation": s(it.get("audio", ""))
    pl = os.path.join(root, "data", "placement.json")
    if os.path.exists(pl):
        for d in json.load(open(pl, encoding="utf-8")).get("dictation", []): s(d["audio"])
    s("{日本語|にほんご}を{少|すこ}し{話|はな}します。")   # Settings → Test voice
    return words, sents

KANJI = re.compile(r"[㐀-鿿々]")
KANA_ONLY = re.compile(r"^[ぁ-ゟァ-ヿー]+$")
def nounish(w, m):
    """same rule as nounish() in index.html: nouns are also recorded with が for 練習 → ピッチ"""
    return not re.match(r"(?i)to\s", m or "") and not (KANJI.search(w) and w.endswith("い"))

def collect_practice(root, words):
    """練習 extras, one voice (冥鳴ひまり): every N5 kanji word, plus word+が for nouns with pitch
    (N5 words and the weeks' card words), so Listen and Pitch work from Week 1."""
    extra = {}
    def add(r, p):
        if r and KANA_ONLY.match(r): extra[key("w|%s|%s" % (r, "" if p is None else p))] = (r, p)
    items = [(e["w"], e["r"], e.get("p"), e.get("m")) for e in json.load(open(os.path.join(root, "data", "vocab.json"), encoding="utf-8")) if e["l"] == 5 and KANJI.search(e["w"])]
    for f in sorted(glob.glob(os.path.join(root, "weeks", "week-*.json"))):
        for c in json.load(open(f, encoding="utf-8")).get("cards", []):
            if c.get("type", "read") == "read" and c.get("reading"): items.append((c["de"], c["reading"], c.get("pitch"), c.get("en")))
    for w, r, p, m in items:
        add(r, p)
        if p is not None and nounish(w, m): add(r + "が", p)
    return {k: v for k, v in extra.items() if k not in words}

def ensure_vv(vv):
    os.makedirs(vv, exist_ok=True)
    def get(url, dest):
        if not os.path.exists(dest): subprocess.run(["curl", "-sSL", "--fail", "-o", dest, url], check=True)
        return dest
    try:
        import voicevox_core  # noqa
    except ImportError:
        whl = get(URLS["wheel"], os.path.join(vv, os.path.basename(URLS["wheel"])))
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", whl], check=True)
    ort_dir = os.path.join(vv, "voicevox_onnxruntime-linux-x64-1.17.3")
    if not os.path.isdir(ort_dir):
        subprocess.run(["tar", "xzf", get(URLS["ort"], os.path.join(vv, "ort.tgz")), "-C", vv], check=True)
    dic = os.path.join(vv, "open_jtalk_dic_utf_8-1.11")
    if not os.path.isdir(dic):
        subprocess.run(["tar", "xzf", get(URLS["dict"], os.path.join(vv, "dict.tgz")), "-C", vv], check=True)
    for n, _ in VOICES.values(): get(URLS["vvm"].format(n=n), os.path.join(vv, "%d.vvm" % n))
    return os.path.join(ort_dir, "lib", "libvoicevox_onnxruntime.so.1.17.3"), dic

VOWEL = {}
for row, v in (("あかさたなはまやらわがざだばぱぁゃ", "a"), ("いきしちにひみりぎじぢびぴぃ", "i"), ("うくすつぬふむゆるぐずづぶぷぅゅ", "u"),
               ("えけせてねへめれげぜでべぺぇ", "e"), ("おこそとのほもよろをごぞどぼぽぉょ", "o")):
    for c in row: VOWEL[c] = v
VCHAR = {"a": "あ", "i": "い", "u": "う", "e": "え", "o": "お"}
def pron(s):
    """rough pronunciation form, so the furigana reading and Open JTalk's output compare fairly"""
    s = hira(re.sub(r"[^぀-ヿ]", "", s)); out = []
    for c in s:
        prev = VOWEL.get(out[-1]) if out else None
        if c == "ー" and prev: c = VCHAR[prev]
        elif c == "う" and prev in ("o", "u"): c = VCHAR[prev]
        elif c == "い" and prev == "e": c = "え"
        elif c == "を": c = "お"
        out.append(c)
    return "".join(out).replace("は", "わ").replace("へ", "え")   # particles; tolerated by the similarity check
def sim(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()

def word_kana(r, p):
    r = kata(r); mor = []
    for ch in r:
        if ch in SMALL and mor: mor[-1] += ch
        else: mor.append(ch)
    n = len(mor); a = n if (p is None or p == 0 or p > n) else p
    return "".join(mor[:a]) + "'" + "".join(mor[a:])

def write_manifest(root, words):
    """audio/words.json: the word keys ("w|reading|pitch") recorded in 冥鳴ひまり; 練習 Listen/Pitch only use these"""
    have = sorted("w|%s|%s" % (r, "" if p is None else p) for k, (r, p) in words.items()
                  if os.path.exists(os.path.join(root, "audio", "himari", k + ".mp3")))
    json.dump({"voice": "himari", "words": have}, open(os.path.join(root, "audio", "words.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=",".join(VOICES)); ap.add_argument("--vv", default="/tmp/voicevox")
    a = ap.parse_args(); root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    words, sents = collect(root)
    extra = collect_practice(root, words)
    todo = {v: [] for v in a.only.split(",")}
    for v in todo:
        os.makedirs(os.path.join(root, "audio", v), exist_ok=True)
        for k in list(words) + list(sents) + (list(extra) if v == "himari" else []):
            if not os.path.exists(os.path.join(root, "audio", v, k + ".mp3")): todo[v].append(k)
    words = dict(words, **extra)
    write_manifest(root, words)
    if not any(todo.values()): print("nothing to do (%d words, %d sentences)" % (len(words), len(sents))); return
    ort_path, dic = ensure_vv(a.vv)
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
    syn = Synthesizer(Onnxruntime.load_once(filename=ort_path), OpenJtalk(dic))
    for v in todo:
        with VoiceModelFile.open(os.path.join(a.vv, "%d.vvm" % VOICES[v][0])) as m: syn.load_voice_model(m)
    made, fallbacks = 0, []
    for v, keys in todo.items():
        style = VOICES[v][1]
        for k in keys:
            if k in words:
                r, p = words[k]
                q = syn.create_audio_query_from_kana(word_kana(r, p), style)
            else:
                t = sents[k]; base = clean(base_of(t)); want = clean(kana_of(t))
                q = syn.create_audio_query(base, style)
                got = "".join(m.text for ap_ in q.accent_phrases for m in ap_.moras)
                if FURI.search(t) and sim(pron(got), pron(want)) < 0.95:
                    fallbacks.append(base); q = syn.create_audio_query(want, style)
            q.speed_scale = SPEED
            wav = syn.synthesis(q, style)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf: tf.write(wav); tmp = tf.name
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-ac", "1", "-b:a", "48k", os.path.join(root, "audio", v, k + ".mp3")], check=True)
            os.unlink(tmp); made += 1
    write_manifest(root, words)
    print("made %d files (%d words, %d sentences known)" % (made, len(words), len(sents)))
    if fallbacks: print("read from kana (Open JTalk disagreed with the furigana):", *sorted(set(fallbacks)), sep="\n  ")

if __name__ == "__main__":
    main()
