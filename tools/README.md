# Tools

## Data (`build_data.py`)
Rebuilds `data/kanji.json`, `data/vocab.json` and `strokes/*.json` from the open sources listed in the main README.
```sh
mkdir -p /tmp/src && cd /tmp/src
curl -sSLO https://raw.githubusercontent.com/davidluzgouveia/kanji-data/master/kanji.json
curl -sSLO https://raw.githubusercontent.com/mifunetoshiro/kanjium/master/data/source_files/raw/accents.txt
for n in 5 4 3 2; do curl -sSLo n$n.csv https://raw.githubusercontent.com/jamsinclair/open-anki-jlpt-decks/main/src/n$n.csv; done
curl -sSLO https://github.com/KanjiVG/kanjivg/releases/download/r20240807/kanjivg-20240807-main.zip && unzip -q kanjivg-20240807-main.zip -d kvg
pip install --break-system-packages svgpathtools
python3 /path/to/repo/tools/build_data.py --src /tmp/src
```
`genki_kanji.py` holds the Genki lesson index. It was written from memory and is **provisional** until it's checked against the books.

## Audio (`make_audio.py`)
```sh
python3 tools/make_audio.py            # both voices; skips files that already exist
```
The first run downloads VOICEVOX CORE 0.16.2, its ONNX Runtime, the Open JTalk dictionary and the two voice models
(1.vvm 冥鳴ひまり, 4.vvm 玄野武宏) from GitHub releases into /tmp/voicevox. Nothing large is stored in this repo.
About 1 s per sentence per voice in the cloud sandbox. Needs ffmpeg.

Audio keys (must match `index.html`):
- sentence: `clean(kana_of(text))` (furigana markup replaced by the readings), as `TTS.say(text)`
- word: `"w|" + clean(reading) + "|" + pitch`, as `TTS.word(de, reading, pitch)`
- key = FNV-1a 32-bit hash of the UTF-8 bytes as 8 hex digits, then `-`, then the byte length.
