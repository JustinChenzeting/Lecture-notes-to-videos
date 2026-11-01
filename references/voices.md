# Voices

Read this when the user names a voice, wants an offline or different narrator, or wants
their own (possibly cloned) voice.

Contents: 1 Engines and defaults · 2 Named voice profiles · 3 Cloned voices · 4 Audition notes

## 1 Engines and defaults

| Engine | Flag | Needs | Notes |
|---|---|---|---|
| Microsoft Edge neural | default (`--tts edge`) | internet | `en-GB-SoniaNeural` at `+10%`, ~165 wpm. Any Edge voice id works: `--voice en-GB-LibbyNeural`, `en-US-AriaNeural`, … |
| Kokoro (offline) | `--tts kokoro` | nothing after setup | `bf_emma` default; also `bf_isabella`, `bf_alice`, `bf_lily`, `bm_george`, `af_heart` (US) … ~3× real time on a laptop CPU |
| macOS `say` | `--tts say` | macOS | `--voice "Daniel"`, etc. Lowest quality; last resort |
| Chatterbox clone | `--voice <profile>` | `lv.py setup --clone` | see §3 |

If Edge fails (offline, service error, or no reply for a line within about 30 s), rendering
falls back to Kokoro `bf_emma` by itself.
`--rate +0%` slows the default voice to ~150 wpm; adjust the word budget in SKILL.md §2 to match.
Chinese lectures have their own default (`zh-CN-YunxiNeural`), offline voice and rules:
[chinese.md §6](chinese.md#6-voice). Other non-English lectures: pick a matching Edge voice
(`de-DE-KatjaNeural`, …) and write the narration in that language; Kokoro's English model is
fixed to British English.

## 2 Named voice profiles

A profile is a folder `voices/<name>/voice.json`. Searched in this order: `WORK/voices/`,
the user's config folder `voices/` (see customization.md), then the skill's `assets/voices/`.
`--voice <name>` matches the folder name, the `label`, or any of the `aliases`
(case and punctuation are ignored), and sets the engine, voice, rate and title-page credit.

```json
{
  "label": "Isabella (British female, Kokoro)",
  "aliases": ["isabella", "bf_isabella"],
  "engine": "kokoro",
  "voice": "bf_isabella",
  "rate": "+10%"
}
```
`engine` is `edge`, `kokoro`, `say` or `chatterbox`. Bundled: `isabella`. Profiles in the
user's config folder are listed by `lv.py doctor`.

## 3 Cloned voices (Chatterbox)

Only clone a real person's voice with that person's permission, and keep the title-page
credit so viewers know the narration is synthetic. Store personal voices in the user's config
folder, never in the skill, so they are not shared when the skill is.

1. One-time install: `python3 <skill-dir>/scripts/lv.py setup --clone` (2-4 GB; MLX on Apple silicon,
   PyTorch on other systems, CUDA if available). The model downloads from Hugging Face.
2. Make `CONFIG/voices/<name>/reference.wav`: 10 s of clean, continuous speech from the
   speaker, mono, 24 kHz (convert with ffmpeg: `-ac 1 -ar 24000`). Level-normalise only;
   denoising lowered speaker similarity in tests (0.65 vs 0.70 cosine).
3. Write `voice.json`:
   ```json
   {
     "label": "Prof. Example",
     "aliases": ["example", "prof example"],
     "engine": "chatterbox",
     "reference": "reference.wav",
     "rate": "+0%",
     "exaggeration": 0.4,
     "cfg_weight": 0.5,
     "credit": "Narration: synthetic voice of Prof.~Example, used with permission"
   }
   ```
4. Render with `--voice example`.

Cloned synthesis is slow: several minutes per minute of narration on the first render
(cached afterwards), and much slower on CPU-only machines. Run `lv.py check` first, then
start the render in the background. Chatterbox paces itself (~185 wpm), so the usual word
budget gives a slightly shorter video. Each sentence is regenerated if its length is
implausible (rambling or truncated takes).

## 4 Audition notes
Free British female options were auditioned (Oct 2026): Edge Sonia (default) and Libby;
Kokoro bf_emma (B−), bf_isabella (C), bf_alice / bf_lily (D) per Kokoro's VOICES.md. Piper,
F5, Sesame, Orpheus and Dia showed no verified British-female advantage; Qwen3-TTS voice
design and Chatterbox Nano are worth a listening test later, not a default.

Chinese (Oct 2026): all Edge zh-CN voices (and two zh-TW) plus eight Kokoro v1.1-zh voices read
the same lever-rule passage in the house style (c prime, X L, alpha, 等于); Edge Yunxi was chosen
by ear. Measured pace on plain Chinese at +0%: Xiaoxiao 253, Yunxi 266, Yunyang 278 characters a
minute. Kokoro's Chinese front end (misaki) silently drops English words unless given an English
pronouncer, so render_lecture.py passes it espeak-ng. For a cloned voice in Chinese, Chatterbox
Multilingual and Qwen3-TTS (mlx-audio) are the candidates to audition; not built yet.
