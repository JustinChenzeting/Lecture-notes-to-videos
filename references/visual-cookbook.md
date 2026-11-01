# Visual cookbook

Short, parametric TikZ/pgfplots patterns. Each is a few lines and turns into motion with
`\lvanim{first}{frames}{...}`, where `\lvt` runs 0→1. Read only the section you need.
Hand-written labels, strokes drawn on, pointers, sliders and camera zooms:
[visual-style.md](visual-style.md).

Contents: 1 Moving state point · 2 Live readout · 3 Progressive curve · 4 Sweeping tie line ·
5 Lattice / dislocation · 6 Path trace (Burgers circuit) · 7 Vector & force arrows ·
8 Pitfalls

Animation budget: 8–16 frames per animation, at most ~6 animations per 10-minute video.
Each frame is a full PDF page (compile ~0.2–1 s per page). Static build-up overlays are
cheaper; animate only when motion *is* the idea (cooling path, glide, sweep, trace).

## 1 Moving state point (cooling path, loading path)
Inside a pgfplots `axis`, drawing is deferred to `\end{axis}`: put math directly in
coordinates using the global `\lvt`; branch with `\pgfmathparse` + `\ifdim` around whole
commands (helper macros set with `\pgfmathsetmacro` are lost by then).
```latex
\lvanim{3}{10}{%
  \draw[blu,very thick] (axis cs:50,8.7)--(axis cs:50,{8.7-5.7*\lvt});
  \node[dot] at (axis cs:50,{8.7-5.7*\lvt}) {};
  \pgfmathparse{8.7-5.7*\lvt}\let\T\pgfmathresult
  \ifdim\T pt<7.68pt \node[note,blu,right] at (axis cs:51,7.85) {first solid};\fi}
```
Pair with `\say<3-12>{...}` that narrates what happens as the point moves.
Plain `tikzpicture` (no axis) has no deferral: `\pgfmathsetmacro` helpers are fine there.

## 2 Live readout (numbers that update with the motion)
```latex
\lvanim{2}{12}{\pgfmathparse{(50-(20+10*\lvt))/(85-(20+10*\lvt))}\let\xs\pgfmathresult
  \edef\lvtmp{\noexpand\node[note,anchor=west] at (axis cs:60,8)
    {$X_S=\noexpand\pgfmathprintnumber[fixed,precision=2]{\xs}$};}\lvtmp}
```
`\edef` freezes the value before pgfplots defers the node. Readouts are the cheapest way to
make a formula feel alive; compute them from the slide's equation, never hard-code.

## 3 Progressive curve (stress–strain, solubility vs T)
```latex
\lvanim{2}{12}{\addplot[accent,very thick,domain=0:{0.001+0.2*\lvt},samples=40]
  {200*(1-exp(-x/0.02))};}
```
`domain` must not be empty on frame 0 (hence `0.001+`).

## 4 Sweeping tie line (lever rule as temperature changes)
Recompute both phase-boundary compositions from the same functions used to draw the
boundaries (declare them once with `declare function`), so the line always touches the curves.
```latex
\pgfplotsset{declare function={L(\u)=4+4*(1-(1-\u/100)^3.63);}}
```

## 5 Lattice / dislocation
See `assets/template.tex` (`\lattice{core}`): index-based columns (never clip by position),
sigmoid shift of the upper half around the core, small Gaussian strain bump, clamp `exp`
arguments to ±9. The same idea covers screw dislocations (shift along a second axis drawn
in perspective), vacancy hops (one atom moves along an arc), and precipitates (fill a disc
of atoms with `atomB`). Keep ≤ 150 atoms per frame for fast compiles.

## 6 Path trace (Burgers circuit, slip-system walk)
```latex
\def\pts{(0,0),(5,0),(5,5),(0,5),(0,0.1)}  % list your lattice-step corners
\lvanim{2}{10}{\pgfmathsetmacro\n{int(1+4*\lvt)}
  \draw[accent,very thick] (0,0) \foreach \k [count=\i] in \pts {\ifnum\i>\n\else -- \k\fi};}
```
Count lattice steps, not screen distance; label start, finish and the closure vector.

## 7 Vector and force arrows
`\draw[-{Stealth[length=3mm]},accent,very thick] (a) -- ++(\lvt*2,0);` for growing shear,
and resolve onto a plane with `($(a)!\lvt!(b)$)` (calc library).

## 8 Pitfalls (each cost a re-render once)
- A `#` inside a frame body (e.g. `\def\f#1`) breaks beamer: define figure macros in the preamble.
- pgfplots `\addplot coordinates` uses the cycle list; `pd` style already removes markers.
- `exp()` overflows pgfmath beyond ~±10: clamp with `max(-9,min(9,...))`.
- `%`, `&`, `#`, `$` inside `\say{}` are LaTeX syntax: write "percent", "and", etc.
- Every overlay page needs exactly one narration source (`\say` or `\wait`); the renderer
  stops with the page numbers if one is missing.
- Long tick labels collide (`1400`,`1538`): drop one tick or use `xticklabel style={rotate=45}`.
