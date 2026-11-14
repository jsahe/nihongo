# Nihongo

A personal Japanese study app (JLPT N4–N3 → N3, stretch N2) that runs from the iPhone Home Screen:
handwriting practice graded stroke by stroke, FSRS flashcards (vocab reading cards + kanji writing cards),
weekly lessons with furigana shown only on kanji you haven't learned, dictation, pitch accent, and a placement test.

Live: https://jsahe.github.io/nihongo/

- `index.html`: the whole app (vanilla JS, no build step; ts-fsrs inlined). Stores data in localStorage under `nh_` keys.
- `weeks/`: weekly lesson files (`index.json` + `week-NN.json`), generated in the tutor chat.
- `data/`: kanji (N5–N2 + Genki), vocabulary with pitch accent, components, placement items.
- `strokes/`: per-kanji stroke data derived from KanjiVG.
- `audio/<voice>/`: recorded audio (VOICEVOX).
- `tools/`: `build_data.py` (data + strokes), `make_audio.py` (audio), `genki_kanji.py` (provisional Genki lesson index).

## Credits and licenses
- Stroke data: [KanjiVG](https://kanjivg.tagaini.net), © Ulrich Apel, CC BY-SA 3.0. The files in `strokes/` are derived from it and are shared under the same license.
- Kanji data: KANJIDIC2 (EDRDG, CC BY-SA 4.0) via [davidluzgouveia/kanji-data](https://github.com/davidluzgouveia/kanji-data) (MIT).
- Pitch accents: [Kanjium](https://github.com/mifunetoshiro/kanjium), CC BY-SA 4.0.
- JLPT vocabulary lists: Jonathan Waller's JLPT resources (CC BY) via [open-anki-jlpt-decks](https://github.com/jamsinclair/open-anki-jlpt-decks) (MIT).
- Scheduler: [ts-fsrs](https://github.com/open-spaced-repetition/ts-fsrs) (MIT).
- Audio: VOICEVOX:冥鳴ひまり, VOICEVOX:玄野武宏 (generated with VOICEVOX CORE; see each voice's terms).
- No Genki textbook content is included; only lesson numbers are referenced.
