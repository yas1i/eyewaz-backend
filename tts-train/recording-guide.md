# Recording the EYEWAZ base-voice dataset

The voice is only as good as this data. Aim for **one speaker** (clear, neutral
Pakistani Urdu), the **same mic and room** for every session, and accurate
transcripts. Quantity helps — target hours, but you can pilot with ~1 hour.

## Speaker & setup
- One consistent speaker for the whole base voice (a different speaker = a
  different voice — do those separately for dialects).
- Quiet, soft room (no echo/fans/AC hum). A USB condenser mic ~20 cm away with a
  pop filter is ideal; a good phone in a quiet room can work for a pilot.
- Same setup every session: same mic, distance, gain, room. Consistency > gear.
- Speak **naturally and evenly** — neutral, clear, steady pace and tone. This
  *is* the reading voice, so read how you want EYEWAZ to sound.

## How to record
- **One sentence per audio file.** Record a sentence, save it, note its text.
  This makes clean clips + transcripts (what training needs).
- Save as **WAV, mono, 22050 Hz** (or higher — we'll resample). 16-bit.
- Re-record any clip with a stumble, cough, long pause, or noise.
- Leave ~0.2–0.5 s of silence at the start/end; trim long silences.
- Keep clips **2–12 seconds** each (a sentence or two). Avoid very long ones.

## What to read
Use **varied** sentences so the model learns all sounds, numbers, punctuation,
and intonation — statements, questions, lists, numbers, dates, names.
`sentences_urdu.txt` is a starter set; **expand it to hundreds–thousands** of
diverse Urdu sentences (news lines, everyday phrases, the kind of content EYEWAZ
reads). The more varied text you cover, the better the voice generalizes.

## Folder layout to hand off
```
raw/
  0001.wav
  0002.wav
  ...
metadata.csv          # one line per clip:  id|exact transcript
```
`metadata.csv` (LJSpeech format — `id` = filename without .wav):
```
0001|السلام علیکم، ای ویواز میں خوش آمدید۔
0002|آج کا درجہ حرارت پینتیس ڈگری ہے۔
```
**The transcript must match the audio exactly** (including the words for any
numbers you spoke). Then run `prepare_dataset.py`.

## Targets
| Stage | Audio (one speaker) | Result |
|---|---|---|
| Pilot | ~1 hour (~600–800 clips) | usable fine-tuned voice |
| Good | ~5 hours | clearly natural |
| Azure-ish | ~10–20+ hours | best quality |

## Consent
The speaker signs the consent form in `docs/voice-bank/consent-form.md` (their
voice becomes the EYEWAZ synthetic voice).
