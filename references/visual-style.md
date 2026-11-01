# Visual style: teaching like Khan Academy and Brilliant

Read this before planning any lecture (both levels). It turns "slides with narration" into a
lesson a viewer can follow by watching: what to show, in what order, and the commands that make
the picture move with the voice. Elaborated lectures add animated scenes on top
([scenes.md](scenes.md)); everything here still applies.

Contents: 1 Principles · 2 Tools · 3 Patterns · 4 Budget and pitfalls

## 1 Principles (what the good ones do, and why)
1. **Concrete before abstract.** Show the thing first (blocks, a lattice, a tank, a cart on a
   slope), then name it, then write the symbol. Symbols mean something only after the viewer has
   seen what they stand for.
2. **One colour per idea, everywhere.** If hundreds are green in the picture, the "200" in the
   sum, the word "hundreds" and the term in the equation are green too. Colour does the linking
   the viewer would otherwise do in their head. Use the palette: `blu`, `grn`, `gold`, `accent`
   (red), at most four meanings per frame; `ink` for everything neutral.
3. **Say it and show it at the same moment.** A label or an equation appears (hand-written,
   `\lvwrite`) while the narration says it; a pointer or halo marks what "this" refers to. The
   eye should never hunt.
4. **Zoom in to work, pull back to conclude.** Move the camera to the part being discussed
   (`\lvzoom`), then return to the whole picture for the result. The whole picture at the end
   is where the pieces click together.
5. **Count and build out loud.** Build results term by term in front of the viewer
   ("two thousand, plus two hundred, plus fifty, plus nine") instead of revealing a finished
   line.
6. **Predict, then reveal** (Brilliant). Before showing what happens, pose the question on the
   slide ("Predict: what happens to the curve as a turns negative?"), give a beat to think,
   then show it. Checkpoints (§4 of SKILL.md) are the formal version; small predictions can
   appear in any frame.
7. **Show change by changing something.** When an idea is "how does X depend on a?", sweep `a`
   with a slider (`\lvslider`) and let the picture respond, leaving faint copies of earlier
   states to compare.
8. **One idea per screen, little text.** The picture carries the idea; the bullets beside it
   (SKILL.md §3) hold what a viewer needs when revising. Keep the question or goal of the frame
   visible at the top while you work on it.
9. **Make the reasoning audible.** Name the object, state the governing rule, and explain
   why the next step follows. Use stable names and one new relationship per spoken beat.
   See [learning-design.md](learning-design.md) for speech examples and the clarity check.
10. **Hold the completed picture.** After a major demonstration, connect its physical meaning,
   governing principle and conditions of use. Add a still, silent reflection beat before
   advancing; keep the final state visible throughout it.

## 2 Tools (all in `lecturevideo.sty`; no downloads)
| Command | What it does |
|---|---|
| `\lvwrite{first}{frames}{content}` | content appears left to right as if hand-written over `frames` pages, then stays. Text, maths or a TikZ node's text: `\node[gold] at (2,3) {\lvwrite{2}{6}{tens}};` |
| `\lvdraw[style]{fraction}{path}` | the first `fraction` of a TikZ path; inside `\lvanim` with `\lvt` it draws a stroke on. Arrowheads appear at the end. Not inside a pgfplots axis (there, grow the `domain`: visual-cookbook §3) |
| `\lvcursor{(x,y)}` | an arrow pointer with its tip at a point; move it with `\lvanim` and `($(a)!\lvt!(b)$)` |
| `\lvhalo{(x,y)}` | a soft red ring marking a spot ("this one") |
| `\lvslider{(at)}{min}{max}{value}{name}` | a parameter slider with a readout "name = value"; sweep it with `\lvanim` |
| `\lvzoom<pages>{x}{y}{zoom}` | on those pages the camera moves smoothly to the point (x, y) of the slide (fractions, 0,0 top left) magnified `zoom` times (1-3); other pages show the whole slide again, with a smooth pull-back |
| soft fades | automatic: every slide change dissolves over 0.25 s (`--fade 0` for hard cuts) |

Pages made by `\lvwrite` and `\lvanim` are one animation: narrate them with **one**
`\say<first-last>{...}`; the renderer spreads the motion over ~80% of that sentence (up to 24
frames a second), so the writing keeps pace with the voice. 6-10 frames suit a word or a short
equation; 12-24 a stroke or a sweep.

`\lvzoom` coordinates: read them off the contact sheet. The slide is 1 wide and 1 tall; the
left column of a two-column frame is around x = 0.3, the right around x = 0.75, and a figure
under the title sits around y = 0.5. Zoom 1.6-2.2 is usually right; past 2.5 the frame shows
very little.

## 3 Patterns
**Concrete build with colour coding and a running sum** (place value, energy bookkeeping, a
mass balance):
```latex
\begin{frame}{What number do the blocks show?}
\say<1>{So here we have some blocks: two flats, five rods and nine little cubes.}
\say<2-7>{Let's start with the ones. Count them with me: one, two, three, all the way to nine.}
\say<8>{Each rod is ten. Ten, twenty, thirty, forty, fifty.}
\say<9>{Put it together: two hundred, plus fifty, plus nine. Two hundred fifty nine.}
\lvzoom<2-7>{0.62}{0.5}{2}\lvzoom<8>{0.45}{0.5}{1.8}
\centering
\begin{tikzpicture}[x=0.5cm,y=0.5cm]
  \useasboundingbox (-0.5,-3) rectangle (14.5,4.5);   % fixed size, so nothing jumps
  \foreach \i in {0,1} \fill[grn!35,draw=grn] (\i*3.4,0) rectangle ++(3,3);
  \foreach \i in {0,...,4} \fill[gold!40,draw=gold] ({7.2+\i*0.8},0) rectangle ++(0.5,3);
  \foreach \i in {0,...,8} \fill[accent!40,draw=accent] ({11.8+mod(\i,3)*0.7},{int(\i/3)*0.7}) rectangle ++(0.5,0.5);
  \node[accent,font=\itshape] at (12.6,3.6) {\lvwrite{2}{6}{ones}};
  \only<8->{\node[gold,font=\itshape] at (8.8,3.6) {tens};}
  \only<9>{\node[font=\Large] at (8,-2) {$\textcolor{grn}{200}+\textcolor{gold}{50}+\textcolor{accent}{9}=\mathbf{259}$};}
\end{tikzpicture}
\end{frame}
```
**Point while you explain** (a diagram with several parts): one `\say` per part, and on each
page `\lvhalo` on the part being named, or a cursor gliding to it:
`\lvanim{3}{8}{\lvcursor{($(lever)!\lvt!(fulcrum)$)}}` with `\say<3-10>{...}`.

**Brief prediction** (additional to the actual homework attempts): page 1 shows the setup and a line in the accent colour,
`{\color{accent}\itshape Predict:} what happens when …?`, narrated as a question with a short
`\wait<2>{2}`; the reveal follows on page 3.

**Sweep a parameter** (how does the graph depend on a?):
```latex
\say<1-16>{Watch the curve as a grows from one half to two: the parabola gets narrower.}
\begin{tikzpicture}
  \begin{axis}[pd,width=7cm,height=5cm,ymin=0,ymax=4,domain=-2:2,samples=60]
    \addplot[accent!30] {0.5*x^2};                                  % faint copy of the start
    \lvanim{1}{16}{\addplot[accent,very thick] {(0.5+1.5*\lvt)*x^2};}
  \end{axis}
  \lvanim{1}{16}{\lvslider{(0.5,-1.3)}{0}{2}{0.5+1.5*\lvt}{a}}
\end{tikzpicture}
```
**Draw the path of a process** (a cooling path, a cycle on a P-V diagram, a free-body force):
`\lvanim{2}{16}{\lvdraw[accent,very thick,-{Stealth}]{\lvt}{(0,0) .. controls (2,3) .. (4,1)}}`.

## 4 Budget and pitfalls
- Per 10 minutes: hand-written labels and equations wherever a key term or result first
  appears (8-15), 3-6 camera moves, 2-4 pointer or halo sequences, 1-3 sweeps. More turns into
  noise; static build-ups stay the backbone.
- **Keep the picture still.** When later pages add a label or an equation outside the
  drawing, the whole picture shifts unless its size is fixed: start the tikzpicture with
  `\useasboundingbox (x1,y1) rectangle (x2,y2);` covering everything any page will show.
  Check on the contact sheet that consecutive pages line up.
- Every page needs narration: a `\lvwrite` or `\lvanim` run is covered by one ranged `\say`.
- A `\lvzoom` page must still make sense on its own in the PDF handout (it is unzoomed there).
- Colours must agree everywhere: picture, slide text (`\textcolor{grn}{...}`) and spoken
  wording ("the green flats").
- Don't zoom on a page that has an animation you want seen whole, or on the title page.
