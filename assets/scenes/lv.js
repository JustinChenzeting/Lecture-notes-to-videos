/* lv.js - the scene kit of lecture-notes-to-video (references/scenes.md).
 *
 * A scene is a 1920x1080 page whose picture is a pure function of time. Build the picture once,
 * then describe each narrated beat with LV.beat(b => ...): beat k is spoken by the k-th \say of
 * the frame that holds \lvscene. The renderer measures each beat, times it to its sentence and
 * seeks frame by frame, so never animate with timers, requestAnimationFrame or Date.
 *
 *   LV.beat(b => { b.show(node, 0); b.write(label, 400); b.look(cam, 700, 500, 1.8, 900); }, {hold: 2000})
 *   LV.frame((t, lv) => { ... })   // redraw a canvas or three.js scene at time t (seconds)
 *   LV.done()                      // last line of the scene
 *
 * Times inside a beat are milliseconds from the start of that beat. Needs anime.js loaded first.
 */
(function () {
  const C = { paper: "#FBF9F1", ink: "#222222", accent: "#B31B1B", mute: "#595959", blu: "#006699",
              grn: "#4B7B2B", gold: "#D47500", light: "#F7F7F7", rule: "#CCCCCC" };
  const NS = "http://www.w3.org/2000/svg";
  const W = 1920, H = 1080;

  // The slides' typefaces (TeX Gyre Pagella headings, Source Sans body) from the TeX installation,
  // Noto SC for Chinese, KaTeX's Computer Modern as the fallback that is always there.
  const face = (fam, file, extra = "") => `@font-face{font-family:"${fam}";src:url(/texfont/${file});${extra}}`;
  const style = document.createElement("style");
  style.textContent = [
    face("LV Serif", "texgyrepagella-regular.otf"), face("LV Serif", "texgyrepagella-italic.otf", "font-style:italic"),
    face("LV Serif", "texgyrepagella-bold.otf", "font-weight:bold"),
    face("LV Sans", "SourceSansPro-Regular.otf"), face("LV Sans", "SourceSansPro-Semibold.otf", "font-weight:600"),
    face("LV Sans", "SourceSansPro-Bold.otf", "font-weight:bold"),
    `@font-face{font-family:"LV CJK";src:url(/fonts/NotoSansSC-Regular.otf)}`,
    `@font-face{font-family:"LV CJK";font-weight:bold;src:url(/fonts/NotoSansSC-Bold.otf)}`,
    `@font-face{font-family:"LV CJK Serif";src:url(/fonts/NotoSerifSC-Regular.otf)}`,
    `html,body{margin:0;width:${W}px;height:${H}px;overflow:hidden;background:${C.paper};color:${C.ink}}`,
    `body{font-family:"LV Sans","LV CJK",KaTeX_Main,sans-serif;font-size:44px}`,
    `.serif{font-family:"LV Serif","LV CJK Serif",KaTeX_Main,serif}`,
    `.lv-abs{position:absolute}`,
  ].join("\n");
  document.head.appendChild(style);

  // ---------------------------------------------------------------- building the picture
  function el(tag, attrs = {}, parent) {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  }
  let svgRoot = null;
  /** The 1920x1080 SVG stage (created on first use). */
  function stage() {
    if (!svgRoot) {
      svgRoot = el("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: "position:absolute;left:0;top:0" });
      el("defs", {}, svgRoot);
      document.body.prepend(svgRoot);
    }
    return svgRoot;
  }
  /** SVG text; attrs override the defaults (sans, 44px, ink). serif: true for headings. */
  function text(parent, x, y, s, attrs = {}) {
    const { serif, ...rest } = attrs;
    const t = el("text", { x, y, "font-size": 44, fill: C.ink,
      "font-family": serif ? '"LV Serif","LV CJK Serif",KaTeX_Main,serif' : '"LV Sans","LV CJK",KaTeX_Main,sans-serif',
      ...rest }, parent);
    t.textContent = s;
    return t;
  }
  /** KaTeX maths inside the SVG (so the camera moves it too). anchor: "start" | "middle" | "end". */
  function math(parent, tex, x, y, { size = 48, color = C.ink, anchor = "start", display = false } = {}) {
    const fo = el("foreignObject", { x: 0, y: 0, width: 1, height: 1, overflow: "visible" }, parent);
    const div = document.createElement("div");
    div.style.cssText = `display:inline-block;white-space:nowrap;font-size:${size}px;color:${color};line-height:1`;
    window.katex.render(tex, div, { displayMode: display, throwOnError: true });
    fo.appendChild(div);
    fo._place = () => {  // y is the baseline, like SVG text
      const w = div.offsetWidth, h = div.offsetHeight, base = h * 0.78;
      const dx = anchor === "middle" ? -w / 2 : anchor === "end" ? -w : 0;
      fo.setAttribute("x", x + dx); fo.setAttribute("y", y - base);
      fo.setAttribute("width", w + 2); fo.setAttribute("height", h + 2);
    };
    placers.push(fo);
    return fo;
  }
  /** A hex colour mixed with white: pct = percent of the colour kept. */
  const tint = (hex, pct) => "#" + [1, 3, 5].map(i => Math.round(255 - (255 - parseInt(hex.slice(i, i + 2), 16)) * pct / 100)
    .toString(16).padStart(2, "0")).join("");

  // ------------------------------------------------- things re-applied after every seek
  const appliers = [], placers = [], frames = [];
  /** Camera over an SVG group: tween {x, y, s} with b.look(); (x, y) is shown at the centre. */
  function camera(group) {
    const cam = { x: W / 2, y: H / 2, s: 1 };
    appliers.push(() => group.setAttribute("transform", `translate(${W / 2} ${H / 2}) scale(${cam.s}) translate(${-cam.x} ${-cam.y})`));
    return cam;
  }
  /** Khan-style pointer (an arrow cursor). Move it with b.point(); fade it with b.show/b.hide. */
  function pointer(parent, { color = C.ink, scale = 1.4 } = {}) {
    const g = el("g", { opacity: 0 }, parent || stage());
    el("path", { d: "M0 0 L0 34 L9 26 L15 40 L21 37 L15 24 L27 24 Z", fill: "white", stroke: color,
                 "stroke-width": 2.5, "stroke-linejoin": "round" }, g);
    const p = { x: W / 2, y: H / 2, node: g };
    appliers.push(() => g.setAttribute("transform", `translate(${p.x} ${p.y}) scale(${scale})`));
    return p;
  }
  /** A number shown in a text node: tween counter.v and it is printed with `digits` decimals. */
  function counter(node, digits = 0, fmt = v => v.toFixed(digits)) {
    const c = { v: 0 };
    appliers.push(() => { node.textContent = fmt(c.v); });
    return c;
  }
  const frame = fn => frames.push(fn);

  // ------------------------------------------------------------------------- beats
  const beats = [];                      // [{fn, hold}]
  let master = null, starts = [], spans = [];
  const clipped = new WeakMap(), drawn = new WeakMap();
  let clipN = 0;

  function makeB(tl, off) {
    const at = ms => off + (ms || 0);
    const b = {
      /** anime.js: tl.add(targets, params) at `ms` from the beat start. */
      add(targets, params, ms = 0) { tl.add(targets, params, at(ms)); return b; },
      /** Fade nodes in; they stay hidden until then. */
      show(nodes, ms = 0, dur = 450) {
        for (const n of [].concat(nodes)) n.style.opacity = 0;  // tweens do not apply before they start
        tl.add(nodes, { opacity: [0, 1], duration: dur, ease: "outCubic" }, at(ms)); return b; },
      hide(nodes, ms = 0, dur = 350) { tl.add(nodes, { opacity: 0, duration: dur, ease: "inQuad" }, at(ms)); return b; },
      /** Hand-writing reveal, left to right (SVG text, maths or any SVG group). */
      write(node, ms = 0, dur = 600) {
        let r = clipped.get(node);
        if (!r) {
          const bb = node.getBBox(), id = "lvw" + clipN++;
          const cp = el("clipPath", { id }, stage().querySelector("defs"));
          r = el("rect", { x: bb.x - 6, y: bb.y - 12, width: 0, height: bb.height + 24 }, cp);
          r._w = bb.width + 12;
          node.setAttribute("clip-path", `url(#${id})`);
          clipped.set(node, r);
        }
        tl.add(r, { width: [0, r._w], duration: dur, ease: "linear" }, at(ms)); return b;
      },
      /** Draw a stroke (path, line, circle, rect, polyline) from start to end. */
      draw(node, ms = 0, dur = 800) {
        let d = drawn.get(node);
        if (!d) { d = window.anime.createDrawable(node)[0]; drawn.set(node, d); }
        window.anime.set(d, { draw: "0 0" });  // hidden until drawn
        tl.add(d, { draw: ["0 0", "0 1"], duration: dur, ease: "inOutSine" }, at(ms)); return b;
      },
      /** Count: highlight nodes one after another (each `every` ms), e.g. while narration counts. */
      count(nodes, ms = 0, every = 300, fill = C.accent) {
        nodes.forEach((n, i) => tl.add(n, { fill: [n.getAttribute("fill") || C.light, fill], duration: 160, ease: "linear" },
          at(ms + i * every)));
        return b;
      },
      /** Move a pointer to (x, y). */
      point(p, x, y, ms = 0, dur = 700) { tl.add(p, { x, y, duration: dur, ease: "inOutQuad" }, at(ms)); return b; },
      /** Move a camera to look at (x, y) with zoom s. */
      look(cam, x, y, s, ms = 0, dur = 1000) { tl.add(cam, { x, y, s, duration: dur, ease: "inOutCubic" }, at(ms)); return b; },
      /** Make the beat last at least `ms` (for motion drawn in LV.frame, e.g. physics or 3D). */
      hold(ms) { tl.add({ _: 0 }, { _: 1, duration: ms }, at(0)); return b; },
    };
    return b;
  }
  /** Describe one narrated beat. opts.hold: minimum length in ms. */
  function beat(fn, opts = {}) { beats.push({ fn, hold: opts.hold || 0 }); }

  function build(st) {  // one master timeline with every beat at its start time (ms)
    if (master) master.revert();
    master = window.anime.createTimeline({ autoplay: false });
    st.forEach((s, i) => { makeB(master, s).hold(beats[i].hold); beats[i].fn(makeB(master, s)); });
    starts = st;
  }
  function natural() {  // each beat's own length (ms): build it alone, measure, undo
    return beats.map(bt => {
      const tl = window.anime.createTimeline({ autoplay: false });
      makeB(tl, 0).hold(bt.hold || 1); bt.fn(makeB(tl, 0));
      const d = tl.duration; tl.revert(); return d;
    });
  }
  /** Seconds since beat i began (negative before it), and the planned length of beat i. */
  const local = (i, t) => t - (starts[i] || 0) / 1000;
  const span = i => spans[i];
  /** 0..1 through `ms` of beat i (default: its whole planned length), eased if ease is given. */
  function progress(i, t, ms, ease) {
    const p = Math.max(0, Math.min(1, local(i, t) / ((ms ? ms / 1000 : spans[i]) || 1)));
    return ease ? ease(p) : p;
  }
  const smooth = p => p * p * (3 - 2 * p);

  function apply(t) {
    master.seek(Math.max(0, t) * 1000);
    for (const f of appliers) f();
    for (const f of frames) f(t, LV);
  }
  function done() {
    const go = () => {
      for (const fo of placers) fo._place();
      const nat = natural(), gap = 600;
      let s = 0;
      const st = nat.map(d => { const x = s; s += d + gap; return x; });
      spans = nat.map(d => (d + gap) / 1000);
      build(st);
      window.lv = {
        ready: true,
        info: () => ({ beats: nat }),
        // the renderer's timing: start and length of each beat, in seconds
        plan(st2, len) { spans = len; build(st2.map(x => x * 1000)); apply(0); },
        seek(t) { apply(t); return new Promise(r => requestAnimationFrame(() => r())); },
      };
      apply(0);
    };
    const fonts = ["44px 'LV Sans'", "44px 'LV Serif'", "44px KaTeX_Main", "italic 44px KaTeX_Math"];
    Promise.all(fonts.map(f => document.fonts.load(f).catch(() => null))).then(() => document.fonts.ready)
      .then(() => { try { go(); } catch (e) { window.lvError = String(e && e.stack || e); throw e; } });
  }

  // ------------------------------------------------------------ manim-web scenes
  /** A scene written with manim-web (the Manim API in the browser) instead of LV.beat:
   *    LV.manim(async (scene, M, beat) => {
   *      const ax = new M.Axes({ xRange: [-3, 3, 1], yRange: [0, 9, 3] });
   *      await scene.play(new M.Create(ax));
   *      await beat();                      // end of beat 1 (spoken by \say<1>)
   *      await scene.play(new M.Create(ax.plot(x => x * x, { color: LV.C.accent })));
   *      await beat();                      // end of beat 2
   *    });
   *  Call beat() once at the end of every beat; the kit adds the waits that fit each beat to its
   *  sentence. The builder runs again for the final timing, so create objects inside it. */
  function manim(builder, opts = {}) {
    const box = document.createElement("div");
    box.style.cssText = `position:absolute;left:0;top:0;width:${W}px;height:${H}px;overflow:hidden`;
    document.body.prepend(box);
    const hide = document.createElement("style");  // the player's own controls never show in a video
    hide.textContent = "#lv-manim > *:not(canvas):not(div:has(canvas)){display:none!important}";
    box.id = "lv-manim"; document.head.appendChild(hide);
    let M, player, nat = [];
    async function run(lens) {  // lens: seconds per beat, or null to measure each beat's own length
      if (player) player.dispose();
      box.innerHTML = "";
      player = new M.Player(box, { width: W, height: H, backgroundColor: opts.background || C.paper,
                                   autoHideMs: 1, ...opts.player });
      const ends = [];
      await player.sequence(async (scene) => {
        const now = () => player.timeline.getDuration();
        const beat = async () => {
          if (lens) {
            const target = lens.slice(0, ends.length + 1).reduce((a, b) => a + b, 0);
            if (target - now() > 0.01) await scene.wait(target - now());
          }
          ends.push(now());
        };
        await builder(scene, M, beat);
      });
      player.pause();
      return ends;
    }
    const go = async () => {
      M = await import("/lib/manim-web/manim-web.browser.js");
      const ends = await run(null);
      nat = ends.map((e, i) => Math.round((e - (ends[i - 1] || 0)) * 1000));
      window.lv = {
        ready: true,
        info: () => ({ beats: nat }),
        async plan(_starts, lens) { await run(lens.map((x, i) => Math.max(x, nat[i] / 1000))); player.seek(0); },
        seek(t) { player.seek(t); return new Promise(r => requestAnimationFrame(() => r())); },
      };
      player.seek(0);
    };
    document.fonts.ready.then(go).catch(e => { window.lvError = String(e && e.stack || e); });
  }

  window.LV = { C, W, H, el, stage, text, math, tint, camera, pointer, counter, frame, beat, done,
                local, span, progress, smooth, manim };
})();
