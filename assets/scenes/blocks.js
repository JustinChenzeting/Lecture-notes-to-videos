/* blocks.js - ready-made scene parts for lecture-notes-to-video (references/scenes.md §3).
 * Load after lv.js. Everything is drawn on the SVG stage in the lecture palette and redrawn from
 * time t, so the parts work with LV.beat tweens and LV.frame alike.
 *
 *   const ax = LVB.axes(svg, { x: 200, y: 160, width: 900, height: 700, xRange: [-3, 3, 1], yRange: [-4, 4, 1] });
 *   const curve = ax.plot(x => x * x);            // a path; ax.plot(f, attrs, existingPath) redraws it
 *   const s = LVB.slider(svg, { x: 1250, y: 600, min: -2, max: 2, value: 1, name: "a" });
 *   LV.frame(() => ax.plot(x => s.v * x * x, {}, curve));
 *   LV.beat(b => b.add(s, { v: 2, duration: 1500, ease: "inOutSine" }));
 *
 * Parts: axes · slider · ghosts · arrow · placeValue · squaresOnSides · numberRow ·
 *        ode (RK4) · pendulum · spring · projectile · three.js helpers (glowSprite, surface, orbit)
 * Maths-heavy pictures (number lines, planes, function graphs, vectors, equation transforms,
 * 3D axes, molecules, globes) are better made with manim-web: LV.manim (scenes.md §4).
 */
(function () {
  const { C, el, text, tint } = LV;
  const B = {};
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  let uid = 0;

  /** Axes with ticks and optional numbers; X(x), Y(y) map data to stage pixels; plot(f) draws f.
   *  Curves are clipped to the plot area, so steep parts never spill over the slide. */
  B.axes = (parent, o = {}) => {
    const { x = 200, y = 160, width = 900, height = 700, xRange = [-3, 3, 1], yRange = [-3, 3, 1],
            color = C.mute, numbers = true, size = 34, xLabel = "", yLabel = "" } = o;
    const [x0, x1, xs] = xRange, [y0, y1, ys] = yRange;
    const X = v => x + (v - x0) / (x1 - x0) * width, Y = v => y + height - (v - y0) / (y1 - y0) * height;
    const g = el("g", {}, parent);
    const ox = X(clamp(0, x0, x1)), oy = Y(clamp(0, y0, y1));
    const line = { stroke: color, "stroke-width": 2.5 };
    el("line", { x1: x, y1: oy, x2: x + width, y2: oy, ...line }, g);
    el("line", { x1: ox, y1: y, x2: ox, y2: y + height, ...line }, g);
    for (let v = Math.ceil(x0 / xs) * xs; v <= x1 + 1e-9; v += xs) if (Math.abs(v) > 1e-9) {
      el("line", { x1: X(v), y1: oy - 8, x2: X(v), y2: oy + 8, ...line }, g);
      if (numbers) text(g, X(v), oy + size + 10, fmt(v), { "text-anchor": "middle", "font-size": size, fill: color });
    }
    for (let v = Math.ceil(y0 / ys) * ys; v <= y1 + 1e-9; v += ys) if (Math.abs(v) > 1e-9) {
      el("line", { x1: ox - 8, y1: Y(v), x2: ox + 8, y2: Y(v), ...line }, g);
      if (numbers) text(g, ox - 16, Y(v) + size / 3, fmt(v), { "text-anchor": "end", "font-size": size, fill: color });
    }
    if (xLabel) text(g, x + width + 14, oy + 10, xLabel, { "font-size": size + 6, fill: color, "font-style": "italic", serif: true });
    if (yLabel) text(g, ox + 14, y - 10, yLabel, { "font-size": size + 6, fill: color, "font-style": "italic", serif: true });
    const id = "lvclip" + uid++;
    el("rect", { x, y, width, height }, el("clipPath", { id }, LV.stage().querySelector("defs")));
    const curves = el("g", { "clip-path": `url(#${id})` }, parent);
    const pathOf = (f, n = 160) => {  // f may return NaN where nothing should be drawn (yet)
      let d = "", pen = false;
      for (let i = 0; i <= n; i++) {
        const v = x0 + (x1 - x0) * i / n, w = f(v);
        if (!isFinite(w)) { pen = false; continue; }
        const py = clamp(Y(w), y - height, y + 2 * height);  // keep huge values finite
        d += (pen ? "L" : "M") + X(v).toFixed(1) + " " + py.toFixed(1);
        pen = true;
      }
      return d || "M0 0";
    };
    const plot = (f, attrs = {}, path) => {
      path = path || el("path", { fill: "none", stroke: C.accent, "stroke-width": 6, "stroke-linecap": "round", ...attrs }, curves);
      path.setAttribute("d", pathOf(f));
      return path;
    };
    return { g, curves, X, Y, plot, pathOf, box: { x, y, width, height } };
  };
  const fmt = v => (Math.round(v * 100) / 100).toString().replace("-", "−");

  /** Brilliant-style parameter slider with a readout "name = value". Tween s.v (b.add(s, {v: 2})). */
  B.slider = (parent, o = {}) => {
    const { x = 1250, y = 600, length = 500, min = -2, max = 2, value = 1, name = "a", digits = 2, ticks = true } = o;
    const s = { v: value };
    const g = el("g", {}, parent);
    const sx = v => x + (clamp(v, min, max) - min) / (max - min) * length;
    el("line", { x1: x, y1: y, x2: x + length, y2: y, stroke: C.rule, "stroke-width": 12, "stroke-linecap": "round" }, g);
    const fill = el("line", { y1: y, y2: y, stroke: C.accent, "stroke-width": 12, "stroke-linecap": "round" }, g);
    if (ticks) for (const v of [min, (min + max) / 2, max])
      text(g, sx(v), y + 58, fmt(v), { "text-anchor": "middle", "font-size": 36, fill: C.mute });
    const knob = el("circle", { r: 24, cy: y, fill: "white", stroke: C.accent, "stroke-width": 6 }, g);
    const read = text(g, x, y - 46, "", { "font-size": 50 });
    const zero = sx(clamp(0, min, max));
    LV.frame(() => {
      const k = sx(s.v);
      knob.setAttribute("cx", k);
      fill.setAttribute("x1", Math.min(k, zero)); fill.setAttribute("x2", Math.max(k, zero));
      read.textContent = `${name} = ${fmt(+s.v.toFixed(digits))}`;
    });
    s.g = g;
    return s;
  };

  /** Faint copies of a curve family: mark(b, value, ms) leaves y = f(x, value) behind once reached. */
  B.ghosts = (axes, f, o = {}) => {
    const g = el("g", { fill: "none", stroke: tint(o.color || C.accent, 28), "stroke-width": 3 }, axes.curves);
    axes.curves.insertBefore(g, axes.curves.firstChild);
    const kept = {};
    LV.frame(() => {
      g.innerHTML = "";
      for (const k of Object.values(kept)) if (k.on > 0.5) el("path", { d: axes.pathOf(x => f(x, k.v)) }, g);
    });
    return { mark(b, v, ms) { const k = kept[v] = kept[v] || { v, on: 0 }; b.add(k, { on: [0, 1], duration: 1 }, ms); } };
  };

  /** An arrow you can move every frame: a.set(x1, y1, x2, y2). Hidden when shorter than 4 px. */
  B.arrow = (parent, o = {}) => {
    const { color = C.ink, width = 6, head = 22 } = o;
    const g = el("g", {}, parent);
    const ln = el("line", { stroke: color, "stroke-width": width, "stroke-linecap": "round" }, g);
    const hd = el("polygon", { fill: color }, g);
    return { g, set(x1, y1, x2, y2) {
      const L = Math.hypot(x2 - x1, y2 - y1);
      g.setAttribute("visibility", L < 4 ? "hidden" : "visible");
      if (L < 4) return;
      const a = Math.atan2(y2 - y1, x2 - x1), bx = x2 - head * Math.cos(a), by = y2 - head * Math.sin(a);
      ln.setAttribute("x1", x1); ln.setAttribute("y1", y1); ln.setAttribute("x2", bx); ln.setAttribute("y2", by);
      hd.setAttribute("points", `${x2},${y2} ${bx - head * 0.45 * Math.sin(a)},${by + head * 0.45 * Math.cos(a)} ${bx + head * 0.45 * Math.sin(a)},${by - head * 0.45 * Math.cos(a)}`);
    } };
  };

  /** Base-ten blocks (thousands cubes, hundreds flats, tens rods, ones) standing on a ground line.
   *  Returns { th, h, t, o } (arrays of block groups; each has .front, the face to count with b.count)
   *  and { colour, centre(key), top(key) } for labels. Colours: blue, green, gold, red. */
  B.placeValue = (parent, o = {}) => {
    const { thousands = 0, hundreds = 0, tens = 0, ones = 0, x = 150, ground = 700, unit = 17, gap = 60 } = o;
    const colour = { th: C.blu, h: C.grn, t: C.gold, o: C.accent };
    const U = unit;
    const block = (g, bx, by, nx, ny, nz, col) => {
      const d = U / 2, w = nx * U, h = ny * U, dx = nz * d, dy = -nz * d, ln = { stroke: col, "stroke-width": 1.6 };
      el("polygon", { points: `${bx},${by - h} ${bx + dx},${by - h + dy} ${bx + w + dx},${by - h + dy} ${bx + w},${by - h}`, fill: tint(col, 22), ...ln }, g);
      el("polygon", { points: `${bx + w},${by} ${bx + w},${by - h} ${bx + w + dx},${by - h + dy} ${bx + w + dx},${by + dy}`, fill: tint(col, 45), ...ln }, g);
      const front = el("rect", { x: bx, y: by - h, width: w, height: h, fill: tint(col, 30), ...ln }, g);
      const grid = el("g", { stroke: col, "stroke-width": 0.8, opacity: 0.7 }, g);
      const L = (x1, y1, x2, y2) => el("line", { x1, y1, x2, y2 }, grid);
      for (let i = 1; i < nx; i++) { L(bx + i * U, by, bx + i * U, by - h); L(bx + i * U, by - h, bx + i * U + dx, by - h + dy); }
      for (let j = 1; j < ny; j++) { L(bx, by - j * U, bx + w, by - j * U); L(bx + w, by - j * U, bx + w + dx, by - j * U + dy); }
      for (let k = 1; k < nz; k++) { L(bx + k * d, by - h - k * d, bx + w + k * d, by - h - k * d); L(bx + w + k * d, by - k * d, bx + w + k * d, by - h - k * d); }
      return front;
    };
    const out = { colour, th: [], h: [], t: [], o: [], span: {} };
    let cx = x;
    const put = (key, n, nx, ny, nz, step, perRow = n) => {
      if (!n) return;
      const start = cx;
      for (let i = 0; i < n; i++) {
        const g = el("g", {}, parent);
        const col = i % perRow, row = Math.floor(i / perRow);
        g.front = block(g, cx + col * step, ground - row * (U * 1.75), nx, ny, nz, colour[key]);
        out[key].push(g);
      }
      const cols = Math.min(n, perRow);
      cx += (cols - 1) * step + nx * U + nz * U / 2;
      out.span[key] = [start, cx];
      cx += gap;
    };
    put("th", thousands, 10, 10, 10, 10 * U + 5 * U + 20);
    put("h", hundreds, 10, 10, 1, 10 * U + 30);
    put("t", tens, 1, 10, 1, U * 2.3);
    put("o", ones, 1, 1, 1, U * 1.75, 3);
    out.centre = key => (out.span[key][0] + out.span[key][1]) / 2;
    out.top = key => ({ th: ground - 15 * U, h: ground - 10.5 * U, t: ground - 10.5 * U,
                        o: ground - U * 1.75 * Math.ceil(ones / 3) - U })[key];
    out.width = cx - gap - x;
    return out;
  };

  /** A right triangle with the square on each side (Pythagoras), legs a and b in units of `scale` px.
   *  Returns { tri, sq: {a, b, c}, label: {a, b, c} } for b.show / b.write. */
  B.squaresOnSides = (parent, o = {}) => {
    const { a = 3, b = 4, scale = 60, x = 760, y = 640, colors = { a: C.grn, b: C.grn, c: C.gold } } = o;
    const A = [x, y], Bp = [x + b * scale, y], Cp = [x, y - a * scale];   // right angle at A
    const pt = p => p.join(",");
    const sq = (p, q, col) => {  // square on segment p->q, built outwards (to the right of p->q)
      const dx = q[0] - p[0], dy = q[1] - p[1], r = [q[0] - dy, q[1] + dx], s = [p[0] - dy, p[1] + dx];
      return el("polygon", { points: [p, q, r, s].map(pt).join(" "), fill: tint(col, 35), stroke: col, "stroke-width": 3 }, parent);
    };
    const out = { sq: {
      a: sq(Cp, A, colors.a), b: sq(A, Bp, colors.b), c: sq(Bp, Cp, colors.c) } };
    out.tri = el("polygon", { points: [A, Bp, Cp].map(pt).join(" "), fill: C.paper, stroke: C.ink, "stroke-width": 4 }, parent);
    el("polyline", { points: `${x + 18},${y} ${x + 18},${y - 18} ${x},${y - 18}`, fill: "none", stroke: C.ink, "stroke-width": 2.5 }, parent);
    const cen = p => p.getBBox(), lab = (p, s, col) => { const b = cen(p);
      return LV.math(parent, s, b.x + b.width / 2, b.y + b.height / 2 + 18, { size: 54, color: col, anchor: "middle" }); };
    out.label = { a: lab(out.sq.a, `a^2 = ${a * a}`, colors.a), b: lab(out.sq.b, `b^2 = ${b * b}`, colors.b),
                  c: lab(out.sq.c, `c^2 = ${a * a + b * b}`, colors.c) };
    return out;
  };

  /** A row of n counters (circles) for counting, grouping and sharing; returns the circles. */
  B.numberRow = (parent, o = {}) => {
    const { n = 10, x = 300, y = 540, r = 26, gap = 18, color = C.blu, perRow = 10 } = o;
    return [...Array(n).keys()].map(i => el("circle", { cx: x + (i % perRow) * (2 * r + gap), cy: y + Math.floor(i / perRow) * (2 * r + gap),
      r, fill: tint(color, 35), stroke: color, "stroke-width": 3 }, parent));
  };

  // ------------------------------------------------------------------- physics
  /** Solve y' = f(t, y) once with RK4 at step dt from t = 0 to t1; returns sample(t) (linear
   *  interpolation, clamped). The way myPhysicsLab models pendulums, springs and orbits. */
  B.ode = (f, y0, { t1 = 20, dt = 1 / 240 } = {}) => {
    const ys = [y0.slice()];
    let y = y0.slice();
    const add = (a, b, k) => a.map((v, i) => v + b[i] * k);
    for (let t = 0; t < t1; t += dt) {
      const k1 = f(t, y), k2 = f(t + dt / 2, add(y, k1, dt / 2)), k3 = f(t + dt / 2, add(y, k2, dt / 2)), k4 = f(t + dt, add(y, k3, dt));
      y = y.map((v, i) => v + dt / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]));
      ys.push(y);
    }
    return t => {
      const u = clamp(t / dt, 0, ys.length - 1), i = Math.floor(u), w = u - i, a = ys[i], b = ys[Math.min(i + 1, ys.length - 1)];
      return a.map((v, k) => v + (b[k] - v) * w);
    };
  };

  /** A pendulum (exact equation, optional damping) that swings while the time `run(t)` advances.
   *  draw(seconds since release); also returns state(s) = [angle, angular speed]. */
  B.pendulum = (parent, o = {}) => {
    const { pivot = [960, 220], length = 520, angle = 40, g = 9.8, metres = 1.5, damping = 0, bob = 34,
            trace = true, color = C.blu } = o;
    const w2 = g / metres, th0 = angle * Math.PI / 180;
    const state = B.ode((t, [th, om]) => [om, -w2 * Math.sin(th) - damping * om], [th0, 0], { t1: o.seconds || 30 });
    const gr = el("g", {}, parent);
    el("line", { x1: pivot[0] - 90, y1: pivot[1], x2: pivot[0] + 90, y2: pivot[1], stroke: C.ink, "stroke-width": 6 }, gr);
    const arc = el("path", { fill: "none", stroke: tint(color, 35), "stroke-width": 3, "stroke-dasharray": "8 8" }, gr);
    const rod = el("line", { stroke: C.ink, "stroke-width": 4 }, gr);
    const ball = el("circle", { r: bob, fill: color, stroke: C.ink, "stroke-width": 3 }, gr);
    el("circle", { cx: pivot[0], cy: pivot[1], r: 8, fill: C.ink }, gr);
    const pos = th => [pivot[0] + length * Math.sin(th), pivot[1] + length * Math.cos(th)];
    if (trace) { const a = pos(-th0), b = pos(th0);
      arc.setAttribute("d", `M${a[0]} ${a[1]} A${length} ${length} 0 0 0 ${b[0]} ${b[1]}`); }
    return { g: gr, state, pos, draw(s) {
      const [th] = state(Math.max(0, s)), p = pos(th);
      rod.setAttribute("x1", pivot[0]); rod.setAttribute("y1", pivot[1]); rod.setAttribute("x2", p[0]); rod.setAttribute("y2", p[1]);
      ball.setAttribute("cx", p[0]); ball.setAttribute("cy", p[1]);
      return p;
    } };
  };

  /** A mass on a spring (horizontal), x'' = -(k/m) x - c x'. draw(s) moves it; state(s) = [x, v] in metres. */
  B.spring = (parent, o = {}) => {
    const { wall = 260, y = 600, rest = 560, scale = 260, k = 20, m = 1, x0 = 0.6, damping = 0, coils = 12, color = C.gold } = o;
    const state = B.ode((t, [x, v]) => [v, -(k / m) * x - damping * v], [x0, 0], { t1: o.seconds || 30 });
    const g = el("g", {}, parent);
    el("line", { x1: wall, y1: y - 120, x2: wall, y2: y + 90, stroke: C.ink, "stroke-width": 8 }, g);
    el("line", { x1: wall - 40, y1: y + 90, x2: wall + 1200, y2: y + 90, stroke: C.mute, "stroke-width": 3 }, g);
    const coil = el("polyline", { fill: "none", stroke: C.ink, "stroke-width": 4, "stroke-linejoin": "round" }, g);
    const box = el("rect", { y: y - 70, width: 140, height: 140, rx: 10, fill: tint(color, 45), stroke: color, "stroke-width": 4 }, g);
    const eq = el("line", { x1: wall + rest + 70, y1: y - 110, x2: wall + rest + 70, y2: y + 110, stroke: C.rule, "stroke-width": 3, "stroke-dasharray": "10 8" }, g);
    return { g, state, box, eqLine: eq, draw(s) {
      const [x] = state(Math.max(0, s)), end = wall + rest + x * scale;
      const pts = [[wall, y], [wall + 30, y]];
      const L = end - wall - 60;
      for (let i = 1; i <= coils * 2; i++) pts.push([wall + 30 + L * i / (coils * 2 + 1), y + (i % 2 ? -34 : 34)]);
      pts.push([end - 30, y], [end, y]);
      coil.setAttribute("points", pts.map(p => p.join(",")).join(" "));
      box.setAttribute("x", end);
      return end;
    } };
  };

  /** Projectile with bounces (restitution e), drawn in metres: v0 (m/s), angle (deg), scale (px/m).
   *  draw(s) places the ball, its velocity arrows (vx blue, vy red) and a faint strobe copy every
   *  `strobe` seconds; state(s) = {x, y, vx, vy}. Exact kinematics, no engine needed. */
  B.projectile = (parent, o = {}) => {
    const { v0 = 20, angle = 30, g = 9.8, e = 0, origin = [160, 900], scale = 40, strobe = 0.2,
            color = C.gold, bounces = 3 } = o;
    const k = o.arrowScale || scale * 0.25;  // arrow pixels per m/s
    const a = angle * Math.PI / 180;
    const legs = []; let t0 = 0, x0 = 0, vx = v0 * Math.cos(a), vy = v0 * Math.sin(a);
    for (let i = 0; i <= bounces && vy > 0.3; i++) { const T = 2 * vy / g; legs.push({ t0, x0, vx, vy, T }); t0 += T; x0 += vx * T; vy *= e; }
    const state = s => {
      s = Math.max(0, s);
      let L = legs[legs.length - 1];
      for (const l of legs) if (s < l.t0 + l.T) { L = l; break; }
      const u = Math.min(s - L.t0, L.T);
      return { x: L.x0 + L.vx * u, y: L.vy * u - g * u * u / 2, vx: L.vx, vy: L.vy - g * u };
    };
    const P = st => [origin[0] + st.x * scale, origin[1] - st.y * scale];
    const ghosts = el("g", {}, parent);
    const ball = el("circle", { r: 24, fill: color, stroke: C.ink, "stroke-width": 3 }, parent);
    const ax = B.arrow(parent, { color: C.blu }), ay = B.arrow(parent, { color: C.accent });
    return { state, P, ball, draw(s, { showStrobe = true, strobeArrows = false, showArrows = s > 0 } = {}) {
      const st = state(s), [px, py] = P(st);
      ball.setAttribute("cx", px); ball.setAttribute("cy", py);
      if (showArrows) { ax.set(px, py, px + st.vx * k, py); ay.set(px, py, px, py - st.vy * k); }
      else { ax.set(0, 0, 0, 0); ay.set(0, 0, 0, 0); }
      ghosts.innerHTML = "";
      if (showStrobe) for (let q = strobe; q < s - 1e-6; q += strobe) {
        const sq = state(q), [gx, gy] = P(sq);
        el("circle", { cx: gx, cy: gy, r: 22, fill: tint(color, 40) }, ghosts);
        if (strobeArrows) B.arrow(ghosts, { color: C.blu, width: 4, head: 14 }).set(gx, gy, gx + sq.vx * k, gy);
      }
      return st;
    } };
  };

  // ------------------------------------------------------------- three.js helpers
  /** A soft round particle texture (ThreeUI style) for THREE.PointsMaterial({ map }). */
  B.glowSprite = THREE => {
    const c = document.createElement("canvas"); c.width = c.height = 64;
    const g = c.getContext("2d"), r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(0.4, "rgba(255,255,255,.55)"); r.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = r; g.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(c);
  };
  /** A renderer, scene, lights and camera on the paper background; returns {renderer, scene, camera}. */
  B.three = (THREE, { fov = 38 } = {}) => {
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(LV.W, LV.H); renderer.setPixelRatio(1); renderer.setClearColor(C.paper);
    renderer.domElement.style.cssText = "position:absolute;left:0;top:0";
    document.body.appendChild(renderer.domElement);
    LV.stage().style.zIndex = 2;  // captions above the canvas
    const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(fov, LV.W / LV.H, 0.1, 200);
    scene.add(new THREE.HemisphereLight(0xffffff, 0xd8d2c0, 2.2));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(4, 8, 6); scene.add(sun);
    return { renderer, scene, camera };
  };
  /** z = f(x, y) over [-r, r]^2 as a lit, slightly see-through mesh (maths z is three's y). */
  B.surface = (THREE, f, { r = 2, n = 80, color = 0x8fb8cf, opacity = 0.9 } = {}) => {
    const geo = new THREE.PlaneGeometry(2 * r, 2 * r, n, n).rotateX(-Math.PI / 2), p = geo.attributes.position;
    for (let i = 0; i < p.count; i++) p.setY(i, f(p.getX(i), p.getZ(i)));
    geo.computeVertexNormals();
    return new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color, roughness: 0.55, transparent: true, opacity, side: THREE.DoubleSide }));
  };
  /** Place the camera on a slow orbit: angle in radians, tilt above the horizon, distance. */
  B.orbit = (camera, { angle = 0, tilt = 0.4, dist = 10, target = [0, 1, 0] } = {}) => {
    camera.position.set(target[0] + dist * Math.cos(angle) * Math.cos(tilt), target[1] + dist * Math.sin(tilt),
                        target[2] + dist * Math.sin(angle) * Math.cos(tilt));
    camera.lookAt(...target);
  };

  window.LVB = B;
})();
