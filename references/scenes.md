# Animated scenes (elaborated lectures)

A **scene** is a full-screen animation in the lecture: real motion at 24 frames a second, in
2D, 3D or a physics simulation, timed beat by beat to the narration. Use scenes where motion,
depth or a simulation *is* the idea (place-value blocks being counted, a graph transforming, a
surface sliced by a plane, a projectile's velocity components, a pendulum and its graph, a
molecule turning); keep the rest of the lecture as slides. Everything in
[visual-style.md](visual-style.md) still applies, inside scenes too.

**Build from parts, don't write from scratch.** Most scenes are an example with its numbers and
words changed, a few ready-made blocks (§3), or a manim-web scene (§4). Writing a picture from
raw SVG or three.js is the slow path: take it only for what no part covers.

Contents: 1 How it works · 2 Workflow · 3 Building blocks · 4 manim-web (the Manim API) ·
5 Physics · 6 The kit · 7 Rules · 8 Problems

## 1 How it works
- Each scene is one HTML file, `WORK/scenes/NAME.html`. It is a list of **beats**: beat k is
  narrated by `\say<k>` in the frame holding `\lvscene{NAME}{beats}`.
- The renderer synthesizes the narration first, gives each beat the length of its sentence (or
  of its own motion, if longer), then records the scene frame by frame in a headless browser:
  the installed Chrome, Edge, Chromium or Brave, or Google's headless Chrome fetched once (100-130
  MB download, ~200 MB on disk) when there is none.
- Libraries are fetched once into the cache and served locally, pinned and checksum-verified:
  anime.js, KaTeX, three.js, matter.js (~3 MB, always); cannon-es (0.3 MB), 3Dmol.js (0.5 MB),
  SmilesDrawer (0.2 MB) and manim-web (2.9 MB download) only when a scene uses them. No Node or npm.
- `lv check` saves a still of each beat (`NAME-1.png`, …); the slides and the PDF handout show them.
- Speed: about 1 second of rendering per second of scene at 1080p. Lectures with scenes render at 1080p.
- What good looks like: `<skill-dir>/assets/samples/elaborated-preview.mp4` (55 s, silent).

## 2 Workflow
1. Plan the lecture as usual (SKILL.md §2), then pick **2-6 scenes per 10 minutes**, each
   15-60 s with 2-6 beats. Write each beat's sentence first; the beat then shows exactly that.
2. For each scene pick the route, cheapest first:
   - an **example** that already fits (`<skill-dir>/assets/scenes/examples/`): copy it to
     `WORK/scenes/NAME.html` and change its numbers, words and colours;
   - **maths** (graphs, number lines and planes, vectors, braces, equations that transform, 3D
     axes, charts, tables, molecules, DNA, globes): a manim-web scene (§4);
   - **manipulatives, sliders, physics**: building blocks (§3, §5) on the SVG stage;
   - **custom 3D**: three.js with the helpers in §3.
3. Check it: `lv scene WORK/scenes/NAME.html`. It prints the beats and their own lengths, any
   script error with its line, writes the stills, and a 12-frame contact sheet `NAME-sheet.png`.
   **Look at the sheet**; fix and re-run (2-3 s each).
4. Put it in the lecture, in a plain frame, one `\say` per beat:
   ```latex
   \begin{frame}[plain]
   \lvscene{place-value}{5}
   \say<1>{So here we have several sets of place value blocks. What number do they show?}
   \say<2>{Let's start with the ones. One, two, three, ... nine.}
   ...
   \end{frame}
   ```
5. `lv check` (stills on the contact sheets), then `lv render` as usual.

Examples (each checked and rendered; copy, then edit):
| File | Shows | Built with |
|---|---|---|
| `place-value.html` | Khan-style build: blocks, camera visits, counting, labels written in colour, running sum | `LVB.placeValue`, camera |
| `slider.html` | Brilliant-style "predict, then watch": a slider drives a curve, faint copies stay | `LVB.axes`, `LVB.slider`, `LVB.ghosts` |
| `manim-graph.html` | axes drawn, a graph and its equation written, then transformed | manim-web |
| `pendulum.html` | a pendulum swinging beside the graph of its angle, drawn as it goes | `LVB.pendulum`, `LVB.axes` |
| `projectile.html` | a projectile with live velocity arrows and a strobe | `LVB.projectile` |
| `surface-3d.html` | a 3D surface with glowing particles, then a slicing plane (ThreeUI look) | three.js |
| `tunnelling.html` | a wave packet partly passing a barrier taller than its energy, with the percentages | `LVQ.wave1d`, `LVQ.plot1d` |
| `double-slit.html` | one wave packet through two slits, interfering with itself (brightness probability, colour phase) | `LVQ.wave2d`, `LVQ.plot2d` |
| `phase-diagram.html` | a 40% Sn solder cooling through the Pb-Sn diagram: tie line, lever-rule fractions, grains growing, the eutectic | `LVM.phaseDiagram`, `LVM.microstructure` |
| `dislocation.html` | an edge dislocation gliding through a lattice, a Burgers circuit that fails to close by b, the slip step | `LVM.edgeDislocation` |
| `crystal-cells.html` | an FCC copper cell turning, its close-packed (111) planes, then rock salt read from a POSCAR file | `LVM.cell`, `LVM.crystal3d`, `LVM.structureFile` |
| `molecule-2d.html` | caffeine's skeletal formula drawn bond by bond from SMILES | SmilesDrawer |
| `molecule-3d.html` | ball-and-stick benzene turning edge-on to show it is flat | 3Dmol.js |

## 3 Building blocks (`/kit/blocks.js`, global `LVB`)
Load after `lv.js`: `<script src="/kit/blocks.js"></script>`. Each part draws on the SVG stage
in the palette and returns handles to animate with `b.show`, `b.write`, `b.count`, `b.add`.
| Part | Makes | Returns |
|---|---|---|
| `LVB.axes(svg, {x, y, width, height, xRange:[a,b,step], yRange, numbers, xLabel, yLabel})` | axes with ticks, numbers, clip | `X(x)`, `Y(y)`, `plot(f, attrs, path)` (redraw by passing the same path; `f` may return `NaN` to leave a gap), `pathOf(f)` |
| `LVB.slider(svg, {x, y, length, min, max, value, name})` | parameter slider with readout | `s` with `s.v` to tween: `b.add(s, {v: 2, duration: 1500})` |
| `LVB.ghosts(axes, (x, a) => …)` | faint copies of a curve family | `mark(b, value, ms)`: keep `a = value` once reached |
| `LVB.arrow(svg, {color, width, head})` | an arrow you move each frame | `set(x1, y1, x2, y2)` |
| `LVB.placeValue(svg, {thousands, hundreds, tens, ones, x, ground, unit})` | base-ten blocks in place-value colours | `.th .h .t .o` (block lists, each with `.front` to count), `centre(k)`, `top(k)`, `colour` |
| `LVB.squaresOnSides(svg, {a, b, scale, x, y})` | right triangle with the squares on its sides (Pythagoras) | `tri`, `sq.{a,b,c}`, `label.{a,b,c}` |
| `LVB.numberRow(svg, {n, x, y, perRow, color})` | counters for counting, grouping, sharing | the circles |
| `LVB.three(THREE)`, `LVB.surface(THREE, f, {r})`, `LVB.orbit(camera, {angle, tilt, dist})`, `LVB.glowSprite(THREE)` | three.js setup on the paper background, a lit surface z = f(x, y), a camera orbit, ThreeUI-style particles | objects to add to the scene |

Motion drawn from time goes in `LV.frame(t => …)` (sliders, curves, physics); see the examples.

## 4 manim-web: the Manim API in the browser
[manim-web](https://github.com/maloyan/manim-web) (MIT) ports the Manim library (the engine behind
3Blue1Brown's videos) to the browser: the standard parts of mathematical animation, with Manim's
names. Use it for maths-heavy scenes; it renders in the same recorder with the lecture's
background.
```html
<link rel="stylesheet" href="/lib/katex.min.css">
<script src="/lib/anime.umd.min.js"></script><script src="/lib/katex.min.js"></script><script src="/kit/lv.js"></script>
<script>
LV.manim(async (scene, M, beat) => {
  const ax = new M.Axes({ xRange: [-3, 3, 1], yRange: [0, 9, 3], xLength: 8, yLength: 5, color: LV.C.ink });
  await scene.play(new M.Create(ax, { runTime: 1.2 }));
  await beat();                                         // end of beat 1
  const g = ax.plot(x => x * x, { color: LV.C.accent, strokeWidth: 6 });
  await scene.play(new M.Create(g), new M.Write(new M.MathTex({ latex: "y = x^2", color: LV.C.ink }).moveTo([4.5, 2.5, 0])));
  await beat();                                         // end of beat 2
});
</script>
```
- Call `await beat()` at the end of **every** beat (the number of calls is the beat count). The
  kit adds the waits that fit each beat to its sentence and runs the builder again for the
  final timing, so create every object inside the builder.
- Options are camelCase objects (`xRange`, `runTime`, `fontSize`, `strokeWidth`); positions are
  Manim units, `[x, y, 0]` with the origin at the centre (the frame is about 14 × 8 units).
- Colours: pass the palette (`LV.C.ink`, `accent`, `blu`, `grn`, `gold`); Manim's defaults are
  white for a black background and vanish on the paper.
- Parts: `Axes`, `NumberLine`, `NumberPlane`, `FunctionGraph`, `ParametricFunction`, `Vector`,
  `Arrow`, `Dot`, `Line`, `Brace`, `BraceLabel`, `SurroundingRectangle`, `MathTex`, `Text`,
  `DecimalNumber`, `ValueTracker`, `alwaysRedraw`, `VectorField`, `StreamLines`, `BarChart`,
  `Table`, `Matrix`, `ThreeDAxes`, `Surface3D`; science: `MoleculeMobject` (and `water`,
  `benzene`, …), `BohrDiagram`, `ReactionScheme`, `DNAHelix`, `Cell`, `Globe`.
- Animations: `Create`, `Write`, `FadeIn`, `FadeOut`, `Transform`, `ReplacementTransform`,
  `TransformMatchingTex`, `GrowFromCenter`, `GrowArrow`, `Indicate`, `Circumscribe`,
  `MoveAlongPath`, `Rotate`, `LaggedStart`, `AnimationGroup`; `scene.wait(s)` for pauses inside a beat.
- Full reference: the Manim Community docs (same names, snake_case → camelCase) and
  manim-web's docs at maloyan.github.io/manim-web.

## 5 Physics
| Need | Use |
|---|---|
| Wave packets, tunnelling, the double slit, stationary states | `LVQ` (below) |
| Phase diagrams, crystal structures, dislocations, molecules | `LVM`, SmilesDrawer, 3Dmol.js (below) |
| Pendulums, springs, damped or driven oscillators, orbits, charges in a field: anything given by an equation of motion | `LVB.ode(f, y0, {t1, dt})` (RK4, as myPhysicsLab models them), or the ready `LVB.pendulum` and `LVB.spring` |
| A projectile, with bounces | `LVB.projectile` (exact kinematics) |
| Several bodies colliding, stacking, sliding with friction (2D) | matter.js: `<script src="/lib/matter.min.js">`; simulate once at a fixed step before the beats, store the states, draw the state for `t` |
| Rigid bodies in 3D (falling, rolling, collisions) with three.js | cannon-es: `import * as CANNON from "/lib/cannon-es.js"` in a module script; same pattern: step once, store, draw |

Never step a physics engine inside `LV.frame`: frames are recorded once, in order, and must be
exact; simulate up front and look the state up by time.

**Quantum mechanics** (`/kit/quantum.js`, global `LVQ`; load after `blocks.js`). Natural units
(ħ = m = 1), the particle in a box from −L/2 to L/2. The methods are those of marl0ny's
simulators, re-implemented for frame-exact video: Crank–Nicolson in 1D as in
[QM-Simulator-1D](https://github.com/marl0ny/QM-Simulator-1D) (MIT), Visscher's method in 2D, the
default of [QM-Simulator-2D](https://github.com/marl0ny/QM-Simulator-2D) (BSD-2).
| Part | Makes |
|---|---|
| `LVQ.wave1d({N, L, V, packet: {x0, k0, sigma}})` | a 1D wave packet; `at(t)` gives ψ at simulated time t, `prob(a, b)` the probability between a and b |
| `LVQ.plot1d(svg, sim, {x, y, width, height, energy, parts})` | draws \|ψ\|² filled, the potential in grey, the packet's energy dashed, optionally Re ψ and Im ψ; `draw(t)` |
| `LVQ.wave2d({N, L, V, packet: {x0, y0, kx, ky, sigma}})` and `LVQ.plot2d(sim, {x, y, size, phase})` | a 2D packet on a 256×256 grid, drawn with brightness = probability and colour = phase; walls in ink |
| `LVQ.V.barrier / step / harmonic / doubleWell / doubleSlit / singleSlit / harmonic2d` | ready potentials |
| `LVQ.box(L)`, `LVQ.sho(omega)`, `LVQ.superpose(basis, [{n, c}])` | exact stationary states (`psi(n, x)`, `E(n)`) and superpositions that evolve exactly (same `at(t)`) |

**Materials science and chemistry** (`/kit/materials.js`, global `LVM`; load after `blocks.js`).
Built on [matterviz](https://github.com/janosh/matterviz) (MIT): its core ships with the kit as
`/kit/vendor/matterviz-core.js` (crystal file parsers, bonds, supercells, lattice planes, element
radii and VESTA/Jmol colours, the binary phase-diagram builder) and its data as `/kit/data/`.
`LVM.ready` resolves when it is loaded: build the scene inside `LVM.ready.then(async () => { …; LV.done(); })`
(or `await LVM.ready` in a module script).
| Part | Makes |
|---|---|
| `await LVM.phaseData("Pb-Sn")` | a binary diagram: `Pb-Sn`, `Cu-Zn`, `Fe-Fe3C`, `Al-Cu`, `Al-Si`, `Al-Mg`, `Al-Fe`, `Au-Sn`, `Fe-Ni`, `A-B`; or `"mine.json"` beside the scene (matterviz format: named curves + regions bounded by them) |
| `LVM.phaseDiagram(svg, data, {x, y, width, height, readout:[x, y]})` | regions in the lecture palette, boundaries, eutectic points, axes, labels; `show(c, T)` places the state point with its tie line and lever-rule readout; `tie(c, T)` → `{cL, cR, left, right, fL, fR}`; `at(c, T)` → region |
| `LVM.microstructure(svg, {x, y, r})` | a microscope circle; `set(fSolid, {solid, matrix})` grows grains with the solid fraction |
| `LVM.cell("fcc" / "bcc" / "sc" / "hcp" / "diamond" / "nacl" / "cscl", {a, elements})` | a conventional unit cell as a structure |
| `await LVM.structureFile(url)` | a structure from CIF, POSCAR, XYZ, PDB, mmCIF or JSON (samples in `/kit/data/structures/`: NaCl, BaTiO3, TiO2, LiFePO4, Si); CIF files must list every atom (P1), symmetry is not expanded |
| `LVM.crystal3d(THREE, structure, {scale, scheme, bonds, supercell, planes:[{hkl}], images})` | atoms (radius × scale, VESTA or Jmol colours), bonds, cell edges, a supercell, Miller planes; `images` adds the face/edge/corner atoms of the textbook picture; returns `{group, planes, size}` |
| `LVM.edgeDislocation(svg, {x, y, cols, rows, sp})` | a lattice with an edge dislocation on the slip plane; `draw(core)` glides it; `circuit(i0, j0, w, h, frac)` walks a Burgers circuit (its gap is b) |
| SmilesDrawer: `<script src="/lib/smiles-drawer.min.js">` | 2D skeletal formulas from SMILES into an SVG; draw the bonds on with `b.draw` (`molecule-2d.html`) |
| 3Dmol.js: `<script src="/lib/3Dmol-min.js">` | 3D molecules and proteins from XYZ, SDF, PDB or CIF text; set the view and `render()` in `LV.frame` (`molecule-3d.html`) |
manim-web adds more chemistry (`MoleculeMobject`, `BohrDiagram`, `ReactionScheme`, orbital surfaces).

Pick a simulated-time speed so the motion fills the beats, and cap it before the packet reaches
the outer walls of the box (both examples do: `Math.min(T_MAX, local * SPEED)`). A packet with
wave number k moves at speed k: in L = 1, k = 250 crosses the box in 0.004 time units.

## 6 The kit (`/kit/lv.js`)
Load order: KaTeX css, anime.js, KaTeX, (matter.js, smiles-drawer, 3Dmol), `lv.js`, (`blocks.js`, `quantum.js`, `materials.js`). For three.js add
`<script type="importmap">{"imports":{"three":"/lib/three.module.js"}}</script>` and a
`<script type="module">` with `import * as THREE from "three"`. The page is 1920×1080 on the
lecture's paper colour with the slides' fonts (Pagella for `serif: true`, Source Sans otherwise,
Noto SC for Chinese).

Building the picture (once, outside the beats):
- `LV.stage()`: the SVG stage. `LV.el(tag, attrs, parent)`, `LV.text(parent, x, y, "…", {serif, "font-size", fill, …})`,
  `LV.math(parent, "x^2", x, y, {size, color, anchor})` (KaTeX, moves with the camera).
- `LV.C`: palette (`paper ink accent mute blu grn gold light rule`); `LV.tint(colour, percent)`.
- `LV.camera(group)`: a camera over an SVG group; `LV.pointer()`: a Khan-style cursor;
  `LV.counter(textNode, decimals)`: a number you can tween (`b.add(c, {v: [0, 50]})`).
- `LV.frame((t) => …)`: redraw for time `t` (seconds). `LV.local(k, t)`: seconds since beat k
  began (beats count from 0 here); `LV.progress(k, t, ms, LV.smooth)`: 0→1 over `ms` of beat k.

Beats, in narration order: `LV.beat(b => { … }, {hold: ms})`. Times are milliseconds from
the beat's start:
| Call | Effect |
|---|---|
| `b.show(nodes, ms, dur)` / `b.hide(...)` | fade in (hidden until then) / out |
| `b.write(node, ms, dur)` | hand-writing reveal, left to right |
| `b.draw(path, ms, dur)` | draw a stroke on (path, line, circle, rect) |
| `b.count(nodes, ms, every, colour)` | highlight one after another, in step with counting aloud |
| `b.look(cam, x, y, zoom, ms, dur)` | camera move (zoom in to work, pull back to conclude) |
| `b.point(pointer, x, y, ms, dur)` | move the pointer |
| `b.add(targets, params, ms)` | any anime.js tween (`{opacity: [0, 1], duration: 500, ease: "outCubic"}`), also on plain objects that `LV.frame` reads |
| `b.hold(ms)` | the beat lasts at least this long (motion drawn in `LV.frame`) |

End the script with `LV.done()` (not needed with `LV.manim`).

three.js in the ThreeUI manner (github.com/MengTo/threeui, MIT): soft round particles
(`LVB.glowSprite`), thin orbit lines, halos, a slow camera drift (`LVB.orbit`). On the paper
background use normal blending and palette colours; keep particles under ~5,000. A highlight on a
see-through surface needs `transparent: true, depthTest: false` and `renderOrder = 2`; trace a
curve with `geometry.setDrawRange(0, n)`.

## 7 Rules
- **Time is the only input.** Every frame depends only on `t`: no `requestAnimationFrame`,
  timers, `Date`, or unseeded `Math.random()` (use a formula, or `anime.createSeededRandom(seed)`).
- Build every element before the beats; beats only animate. Elements a beat shows start hidden.
- Same visual language as the slides: palette colours with one meaning each, text at least
  36 px (44 px for labels), the question or goal of the scene at the top, nothing within 60 px
  of the edges.
- A beat shows what its sentence says, in the same order. If the motion needs longer than the
  sentence, the renderer holds the voice; better to write the sentence long enough.
- Chinese scenes: write the text in Chinese; the Noto SC fonts are used automatically.

## 8 Problems
| Symptom | Fix |
|---|---|
| `the scene did not start: ...` with a script error and line | fix the JavaScript; a missing `LV.done()` also lands here |
| `Failed to load resource: ... 404: lib/...` | a path typo: `/lib/anime.umd.min.js`, `/lib/katex.min.js`, `/lib/katex.min.css`, `/lib/matter.min.js`, `/lib/cannon-es.js`, `/lib/three.module.js`, `/kit/lv.js`, `/kit/blocks.js`, `/kit/quantum.js` |
| manim-web: `Cannot read properties of undefined (reading '_dirty')` | an option object passed to `scene.play`; options go to the animation: `new M.Create(x, { runTime: 2 })` |
| manim-web: nothing visible | white default colours on the paper background: pass `color: LV.C.ink` (or another palette colour) |
| `scenes/NAME.html has 4 beats but the lecture says \lvscene{NAME}{5}` | make the beats (`LV.beat` calls or `beat()` calls), the `\lvscene` count and the `\say<k>` lines agree |
| Blank 3D canvas | call `renderer.render(...)` inside `LV.frame`; without a GPU the browser renders in software (slower, same result) |
| The browser does not start (Linux) | headless Chrome needs a few system libraries: `sudo apt-get install -y libnss3 libatk-bridge2.0-0 libgbm1 libxkbcommon0 libasound2t64` (or install Chromium), then retry; or set `LV_CHROME` to a browser |
| Offline | after one online run, scenes work offline; the first one needs internet for the libraries |
