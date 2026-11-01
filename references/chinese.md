# Chinese lectures

Read this when the video's language is Chinese (SKILL.md §0). It replaces SKILL.md's
English-specific rules (word budget, spoken-text rules, checkpoint wording, default voice);
everything else in SKILL.md applies unchanged. For an English video, do not read this file.

Contents: 1 Setup · 2 Length · 3 Narration · 4 Slides · 5 Checkpoints · 6 Voice · 7 Subtitles

## 1 Setup: one option switches everything
`lv init NAME --lang zh` starts from [assets/template-zh.tex](../assets/template-zh.tex), whose
preamble loads `\usepackage[zh]{lecturevideo}`. If `lv init NAME` already ran, run it again with
`--lang zh`: it swaps the template in while `lecture.tex` is still unedited. That option alone
selects XeLaTeX with ctex, Noto Serif SC (titles) and Noto Sans SC (text), the Chinese checkpoint
labels, the Chinese voice, Chinese subtitles and a length estimate in syllables. Do not load
ctex, xeCJK or fontspec, or set fonts, yourself.

- `init --lang zh` downloads the fonts once (~40 MB) and test-builds the Chinese template, so a
  LaTeX without Chinese support shows up before you write anything; its message gives the fix.
  Offline, slides fall back to ctex's default Chinese fonts for the system (macOS and Windows
  fonts, or Fandol on Linux, which TinyTeX installs on demand) and the message says so.
- `check` and `render` print `language: Chinese (...)` first. They stop with a clear message if
  Chinese text appears in a lecture without the option, or the option is set but the narration
  has no Chinese.
- Optional offline voice: `lv setup --zh` (~270 MB; a render with `--tts kokoro` installs it
  itself). Without it, Chinese narration needs internet.

## 2 Length (replaces the word budget in SKILL.md §2)
Chinese is counted in **spoken syllables**: 1 per Chinese character, about 1.7 per English word
(`c prime` is two words) and about 1.3 per digit. The default voice speaks ~265 a minute, so budget
**≈ 250 syllables per minute of speaking time** after subtracting embedded silent holds
from the target video length. Count question reading, pause instructions, explanations and
worked solutions in the narration budget. Manual homework-solving pauses add study time
outside the MP4; report that separately. Maths read in English takes longer than Chinese text,
so derivation frames hold fewer characters than prose frames. `lv check` prints the estimate;
adjust narration if it misses the target by more than ~10%. The estimate runs low when lines are short:
each line adds about 1 s of silence it does not count (measured Oct 2026: a 3-minute lecture of
19 short, letter-heavy lines rendered 12% over its estimate; the template, 1% over). When the user
sets a maximum ("under 3 minutes"), aim 10% below it and check the duration `render` prints.

## 3 Narration (`\say`) (replaces "Spoken text is plain English" in SKILL.md §3)
Use direct spoken Mandarin with explicit nouns and short reasoning steps. Say which quantity
changes and why: “因为只有两相，所以两相的质量分数之和等于 1。” Keep names stable, define new
terms, and coordinate each sentence with the visible diagram. Avoid literary wording and
filler. The shared [learning-design.md](learning-design.md) rules apply, including still
consolidation moments and the spoken clarity check. Explain important equations
mathematically and physically, and sanity-check derivations aloud.

**Maths is read as in the English videos; the operators are read in Chinese.**

| On the slide | In `\say` |
|---|---|
| $c'$, $c''$ | c prime, c double prime |
| $\alpha$, $\beta$, $\Delta G$, $\sigma_y$ | alpha, beta, delta G, sigma y |
| $X_L$, $T_3$ | X L, T three |
| $=$, $\approx$, $\neq$ | 等于, 约等于, 不等于 |
| $+$, $-$, $\times$, $\div$ or $\frac{a}{b}$ | 加, 减, 乘以, a 除以 b |
| $x^2$, $x^3$, $\sqrt{x}$, $10^5$ | x 的平方, x 的立方, 根号 x, 10 的 5 次方 |
| $>$, $<$, $\ge$, $\propto$ | 大于, 小于, 大于等于, 正比于 |
| $\frac{dy}{dx}$, $\int f\,dx$ | y 对 x 求导, f 对 x 积分 |

- Put a space on each side of English letters and words: `所以 c 等于 X L 乘以 c prime`. The
  voice switches language cleanly and the subtitles break between words.
- Numbers are Arabic digits with Chinese units: `779 摄氏度`, `2.5 倍`, `0.31`. Units are spoken
  as Chinese words (摄氏度, 千克, 毫米, 兆帕), not symbols. Write a percent sign as `\%`
  (`35\% B`): a bare `%` starts a LaTeX comment. No other LaTeX in `\say`, and no `&`, `#`, `$`.
- Terminology: the standard mainland Chinese term, with the English term once at its first
  mention, spoken `杠杆定律，也就是 lever rule` and shown `杠杆定律（lever rule）`; Chinese only
  afterwards. If the notes use a different Chinese term, follow the notes.
- English notes made into a Chinese video: translate the meaning, not word for word, and keep
  the notes' symbols and equations unchanged.
- Full-width punctuation (，。：？！) in narration: it sets the pauses and the subtitle breaks.
  Sentences up to ~40 characters sound and subtitle best.
- A misread character (usually a polyphone): only after hearing it, add a line to
  `WORK/lexicon.tsv`, `written<TAB>spoken`, respelling it with a homophone. It changes the audio
  only; subtitles keep the original text.

## 4 Slides
- Chinese text with full-width punctuation; maths stays LaTeX (`$c'$`). Bullets up to ~25
  Chinese characters, frame titles up to ~14. The slides-carry-the-explanation rule of
  SKILL.md §3 applies, with `物理意义：` in the accent colour where English uses `Physically:`.
- Figure labels in Chinese (液相, 固相, 滑移面); axis symbols stay maths.
- Chinese has no italics, so `\emph` on Chinese text shows no emphasis: use `\textbf{...}` or
  `{\color{accent}...}`.
- The teaching tools ([visual-style.md](visual-style.md)) and animated scenes
  ([scenes.md](scenes.md)) work unchanged: `\lvwrite{2}{6}{个位}` writes Chinese on too, and scene
  text in Chinese uses the Noto SC fonts automatically. Narrate each scene beat in Chinese.

## 5 Homework retrieval and recall
Ask for the actual homework, preserve its difficulty and exercise IDs, and follow SKILL.md §4
and [learning-design.md](learning-design.md). Use `\attemptq` for new homework questions. In
Chinese it adds a spoken instruction to pause, write a solution or reasoned start, mark where
the learner is stuck, and resume after trying. The same instruction appears on screen. Its
still hold is time to pause the player, not a solving deadline. The separate solution frame
is labelled 答案. Use ordinary frames for long exercises and multi-frame solutions.

Speak the full question, including its numbers. A translated question keeps the original
mathematics, constraints, givens and subparts. Deliver `recall.md` and `recall-answers.md` in
Chinese with the same next-day/about-one-week starting schedule. The legacy `\examq` macro
retains its old silent countdown behavior for existing lectures.

## 6 Voice
- Default: Microsoft Edge `zh-CN-YunxiNeural` (male, bright) at `+0%`, chosen by ear from all
  Edge Chinese voices (Oct 2026). Others: `zh-CN-XiaoxiaoNeural` (female, warm),
  `zh-CN-YunyangNeural` (male, newsreader), `zh-CN-XiaoyiNeural`, `zh-CN-YunjianNeural`,
  `zh-CN-YunxiaNeural`; Taiwan Mandarin `zh-TW-HsiaoChenNeural`, `zh-TW-YunJheNeural`.
  Choose one with `--voice <id>`.
- A personal default goes in config.json under `"zh"` (references/customization.md). The
  top-level `voice`/`tts`/`rate` keys apply to English lectures only.
- Offline: Kokoro v1.1-zh (`lv setup --zh`), default `zm_009`; `zf_001`…`zf_099` are female and
  `zm_009`…`zm_100` male. Used automatically when Edge is unreachable, or with `--tts kokoro`.
- Cloned voices speak English only, and English voices cannot read Chinese: `render` refuses both
  for a Chinese lecture (macOS `say` only with a Chinese voice, e.g. `--tts say --voice Tingting`).

## 7 Subtitles
Automatic, after Netflix's Simplified Chinese guide: at most 16 characters a line (Latin letters
count half) and two lines, commas and full stops shown as spaces, breaks only between words
(Edge's word timings, or jieba offline), each cue timed to the word. Subtitles show the
narration as written ("c prime 等于 X L 乘以 c prime"), and the subtitle track is tagged Chinese.
