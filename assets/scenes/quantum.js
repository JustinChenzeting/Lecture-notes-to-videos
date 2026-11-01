/* quantum.js - quantum-mechanics parts for scenes (references/scenes.md §5). Load after lv.js and
 * blocks.js. Global LVQ. Natural units (hbar = m = 1); the particle lives in a box with walls.
 *
 * Methods follow marl0ny's simulators (re-implemented here for exact, frame-by-frame video):
 *  - 1D: Crank-Nicolson time evolution, as in QM-Simulator-1D (MIT, github.com/marl0ny/QM-Simulator-1D;
 *    M. Newman, Computational Physics, ch. 9).
 *  - 2D: Visscher's explicit method (real and imaginary parts updated in turn), the default of
 *    QM-Simulator-2D (BSD-2-Clause, github.com/marl0ny/QM-Simulator-2D; P. Visscher, Computers in
 *    Physics 5, 596 (1991)).
 *  - Stationary states of the box and the harmonic oscillator are exact formulas.
 *
 *   const sim = LVQ.wave1d({ V: LVQ.V.barrier(0.1, 0.02, 4e4), packet: { x0: -0.25, k0: 250, sigma: 0.04 } });
 *   const view = LVQ.plot1d(svg, sim, { x: 160, y: 200, width: 1600, height: 640 });
 *   LV.frame(t => view.draw(LV.local(1, t) * 0.0012));   // simulated time for this frame
 *
 * Simulated time only ever moves forward between frames (the renderer records frames in order);
 * going back restarts from t = 0, so every frame is exact and repeatable.
 */
(function () {
  const { C, el, tint } = LV;
  const Q = {};

  // ------------------------------------------------------------------ potentials
  /** Potentials V(x) (1D, x in [-L/2, L/2]) and V(x, y) (2D). Heights in natural units. */
  Q.V = {
    free: () => () => 0,
    barrier: (x0 = 0, width = 0.02, height = 4e4) => x => (Math.abs(x - x0) < width / 2 ? height : 0),
    step: (x0 = 0, height = 2e4) => x => (x > x0 ? height : 0),
    harmonic: (omega = 600) => x => 0.5 * omega * omega * x * x,
    doubleWell: (a = 0.15, depth = 3e4) => x => depth * ((x * x - a * a) / (a * a)) ** 2 / 4,
    /** 2D: a wall at x = wallX with two slits (centred at y = +-separation/2). */
    doubleSlit: ({ wallX = 0, thickness = 0.02, slit = 0.04, separation = 0.16, height = 1e5 } = {}) => (x, y) =>
      Math.abs(x - wallX) < thickness / 2 && !(Math.abs(Math.abs(y) - separation / 2) < slit / 2) ? height : 0,
    singleSlit: ({ wallX = 0, thickness = 0.02, slit = 0.06, height = 1e5 } = {}) => (x, y) =>
      Math.abs(x - wallX) < thickness / 2 && Math.abs(y) > slit / 2 ? height : 0,
    harmonic2d: (omega = 400) => (x, y) => 0.5 * omega * omega * (x * x + y * y),
  };

  // ------------------------------------------------------------- 1D: Crank-Nicolson
  /** A wave packet in a 1D box [-L/2, L/2] (psi = 0 at the walls).
   *  opts: N grid points, L, V(x), packet {x0, k0, sigma} or psi0(x) -> [re, im], dt.
   *  at(t) -> { re, im } at simulated time t; prob(a, b) -> probability between x = a and b. */
  Q.wave1d = (o = {}) => {
    const N = o.N || 1024, L = o.L || 1, dx = L / (N + 1), dt = o.dt || 1e-5, V = o.V || Q.V.free();
    const xs = Float64Array.from({ length: N }, (_, i) => -L / 2 + (i + 1) * dx);
    const vs = xs.map(V);
    const p = o.packet || { x0: -0.25, k0: 200, sigma: 0.04 };
    const init = o.psi0 || (x => { const g = Math.exp(-((x - p.x0) ** 2) / (4 * p.sigma * p.sigma)); return [g * Math.cos(p.k0 * x), g * Math.sin(p.k0 * x)]; });
    // (1 + iH dt/2) psi_new = (1 - iH dt/2) psi_old, H = -1/2 d2/dx2 + V: tridiagonal, Thomas algorithm
    const a = dt / (4 * dx * dx);                                   // off-diagonal factor, times i
    const dr = new Float64Array(N), di = new Float64Array(N);       // left diagonal 1 + i(dt/2)(1/dx^2 + V)
    for (let j = 0; j < N; j++) { dr[j] = 1; di[j] = (dt / 2) * (1 / (dx * dx) + vs[j]); }
    // pre-factor the left matrix: c' coefficients of the Thomas algorithm (complex)
    const cr = new Float64Array(N), ci = new Float64Array(N), mr = new Float64Array(N), mi = new Float64Array(N);
    { // sub- and super-diagonal are both -i a
      let pr = dr[0], pi = di[0];
      for (let j = 0; j < N; j++) {
        if (j > 0) { // m_j = d_j - (-ia) * c'_{j-1}
          pr = dr[j] - a * ci[j - 1]; pi = di[j] + a * cr[j - 1];
        }
        mr[j] = pr; mi[j] = pi;
        const den = pr * pr + pi * pi;          // c'_j = (-ia) / m_j
        cr[j] = (-a * pi) / den; ci[j] = (-a * pr) / den;
      }
    }
    let re = new Float64Array(N), im = new Float64Array(N), t = 0;
    const reset = () => {
      let s = 0;
      for (let j = 0; j < N; j++) { const [u, w] = init(xs[j]); re[j] = u; im[j] = w; s += u * u + w * w; }
      s = Math.sqrt(s * dx); for (let j = 0; j < N; j++) { re[j] /= s; im[j] /= s; }
      t = 0;
    };
    const br = new Float64Array(N), bi = new Float64Array(N);
    const step = () => {
      for (let j = 0; j < N; j++) { // b = (1 - iH dt/2) psi
        const lr = j > 0 ? re[j - 1] : 0, li = j > 0 ? im[j - 1] : 0, rr = j < N - 1 ? re[j + 1] : 0, ri = j < N - 1 ? im[j + 1] : 0;
        const hr = (dt / 2) * (1 / (dx * dx) + vs[j]);
        // (1 - i hr) psi_j + i a (psi_{j-1} + psi_{j+1})
        br[j] = re[j] + hr * im[j] - a * (li + ri);
        bi[j] = im[j] - hr * re[j] + a * (lr + rr);
      }
      // forward sweep: y_j = (b_j - (-ia) y_{j-1}) / m_j
      for (let j = 0; j < N; j++) {
        let ur = br[j], ui = bi[j];
        if (j > 0) { ur -= a * bi[j - 1]; ui += a * br[j - 1]; }   // + i a y_{j-1}
        const den = mr[j] * mr[j] + mi[j] * mi[j];
        br[j] = (ur * mr[j] + ui * mi[j]) / den; bi[j] = (ui * mr[j] - ur * mi[j]) / den;
      }
      for (let j = N - 2; j >= 0; j--) {                          // back substitution
        br[j] -= cr[j] * br[j + 1] - ci[j] * bi[j + 1];
        bi[j] -= cr[j] * bi[j + 1] + ci[j] * br[j + 1];
      }
      re.set(br); im.set(bi); t += dt;
    };
    reset();
    const sim = {
      N, L, dx, xs, vs, V,
      at(tt) { if (tt < t - dt / 2) reset(); while (t < tt - dt / 2) step(); return { re, im, t }; },
      prob(lo, hi) { let s = 0; for (let j = 0; j < N; j++) if (xs[j] >= lo && xs[j] < hi) s += re[j] * re[j] + im[j] * im[j]; return s * dx; },
    };
    return sim;
  };

  // ------------------------------------------------------- exact stationary states
  const hermite = (n, x) => { let h0 = 1, h1 = 2 * x; if (n === 0) return h0; for (let k = 1; k < n; k++) [h0, h1] = [h1, 2 * x * h1 - 2 * k * h0]; return h1; };
  const fact = n => (n < 2 ? 1 : n * fact(n - 1));
  /** Infinite square well [-L/2, L/2]: psi_n(x), E_n = n^2 pi^2 / (2 L^2), n = 1, 2, ... */
  Q.box = (L = 1) => ({ L, E: n => (n * n * Math.PI * Math.PI) / (2 * L * L),
    psi: (n, x) => (Math.abs(x) > L / 2 ? 0 : Math.sqrt(2 / L) * Math.sin(n * Math.PI * (x + L / 2) / L)) });
  /** Harmonic oscillator V = omega^2 x^2 / 2: psi_n(x), E_n = omega (n + 1/2), n = 0, 1, ... */
  Q.sho = (omega = 600) => ({ omega, E: n => omega * (n + 0.5),
    psi: (n, x) => { const s = Math.sqrt(omega); return (s / Math.PI) ** 0.25 / Math.sqrt(2 ** n * fact(n)) * hermite(n, s * x) * Math.exp(-omega * x * x / 2); } });
  /** A superposition sum c_n psi_n e^{-i E_n t} of stationary states (exact at any t), with the
   *  same at(t) interface as wave1d. terms: [{ n, c }] with real or [re, im] amplitudes. */
  Q.superpose = (basis, terms, { N = 1024, L = basis.L || 1 } = {}) => {
    const dx = L / (N + 1), xs = Float64Array.from({ length: N }, (_, i) => -L / 2 + (i + 1) * dx);
    const cs = terms.map(({ n, c }) => ({ n, cr: Array.isArray(c) ? c[0] : c, ci: Array.isArray(c) ? c[1] : 0, E: basis.E(n),
      f: Float64Array.from(xs, x => basis.psi(n, x)) }));
    const norm = Math.sqrt(cs.reduce((s, k) => s + k.cr * k.cr + k.ci * k.ci, 0)) || 1;
    const re = new Float64Array(N), im = new Float64Array(N);
    return { N, L, dx, xs, vs: basis.omega ? xs.map(x => 0.5 * basis.omega ** 2 * x * x) : new Float64Array(N),
      at(t) {
        re.fill(0); im.fill(0);
        for (const k of cs) { const ph = -k.E * t, ar = (k.cr * Math.cos(ph) - k.ci * Math.sin(ph)) / norm, ai = (k.cr * Math.sin(ph) + k.ci * Math.cos(ph)) / norm;
          for (let j = 0; j < N; j++) { re[j] += ar * k.f[j]; im[j] += ai * k.f[j]; } }
        return { re, im, t };
      },
      prob(lo, hi) { let s = 0; for (let j = 0; j < N; j++) if (xs[j] >= lo && xs[j] < hi) s += re[j] * re[j] + im[j] * im[j]; return s * dx; } };
  };

  /** Draw a 1D simulation on the SVG stage: probability density |psi|^2 (filled), optional real and
   *  imaginary parts, and the potential (grey, scaled to vMax). draw(t) updates it for simulated time t. */
  Q.plot1d = (parent, sim, o = {}) => {
    const { x = 160, y = 200, width = 1600, height = 640, parts = false, potential = true,
            vMax = null, pMax = null, color = C.accent, energy = null } = o;
    const g = el("g", {}, parent);
    const base = y + height, X = v => x + (v + sim.L / 2) / sim.L * width;
    el("line", { x1: x, y1: base, x2: x + width, y2: base, stroke: C.mute, "stroke-width": 2.5 }, g);
    el("line", { x1: x, y1: y - 20, x2: x, y2: base, stroke: C.ink, "stroke-width": 6 }, g);
    el("line", { x1: x + width, y1: y - 20, x2: x + width, y2: base, stroke: C.ink, "stroke-width": 6 }, g);
    const pot = el("path", { fill: tint(C.mute, 22), stroke: C.mute, "stroke-width": 2 }, g);
    const fill = el("path", { fill: tint(color, 35), stroke: color, "stroke-width": 4, "stroke-linejoin": "round" }, g);
    const reP = el("path", { fill: "none", stroke: C.blu, "stroke-width": 3 }, g), imP = el("path", { fill: "none", stroke: C.grn, "stroke-width": 3 }, g);
    const vTop = vMax || Math.max(1e-9, ...sim.vs.filter(isFinite)) * 1.05;
    if (potential && vTop > 1e-6) {
      let d = `M${x} ${base}`;
      for (let j = 0; j < sim.N; j++) d += `L${X(sim.xs[j]).toFixed(1)} ${(base - Math.min(1, sim.vs[j] / vTop) * height * 0.85).toFixed(1)}`;
      pot.setAttribute("d", d + `L${x + width} ${base}Z`);
    }
    if (energy != null && vTop > 1e-6) {  // the packet's energy on the potential's scale
      const ey = base - Math.min(1, energy / vTop) * height * 0.85;
      el("line", { x1: x, y1: ey, x2: x + width, y2: ey, stroke: C.gold, "stroke-width": 3, "stroke-dasharray": "14 10" }, g);
    }
    let pTop = pMax;
    return { g, X, draw(t) {
      const { re, im } = sim.at(t);
      if (!pTop) { pTop = 0; for (let j = 0; j < sim.N; j++) pTop = Math.max(pTop, re[j] * re[j] + im[j] * im[j]); pTop *= 1.15; }
      const step = Math.max(1, Math.floor(sim.N / 600));
      let d = `M${x} ${base}`, dr = "", di = "";
      const amp = Math.sqrt(pTop);
      for (let j = 0; j < sim.N; j += step) {
        const px = X(sim.xs[j]).toFixed(1), pr = re[j] * re[j] + im[j] * im[j];
        d += `L${px} ${(base - Math.min(1.1, pr / pTop) * height * 0.85).toFixed(1)}`;
        if (parts) { const mid = base - height * 0.425;
          dr += (j ? "L" : "M") + px + " " + (mid - re[j] / amp * height * 0.4).toFixed(1);
          di += (j ? "L" : "M") + px + " " + (mid - im[j] / amp * height * 0.4).toFixed(1); }
      }
      fill.setAttribute("d", d + `L${x + width} ${base}Z`);
      reP.setAttribute("d", dr || "M0 0"); imP.setAttribute("d", di || "M0 0");
    } };
  };

  // ------------------------------------------------------------- 2D: Visscher's method
  /** A wave packet in a 2D box [-L/2, L/2]^2: opts N (grid side), L, V(x, y), packet {x0, y0, kx, ky, sigma}.
   *  at(t) -> { re, im } (Float64Array N*N, row-major, y down the rows) at simulated time t. */
  Q.wave2d = (o = {}) => {
    const N = o.N || 256, L = o.L || 1, dx = L / (N + 1), V = o.V || (() => 0);
    const p = o.packet || { x0: -0.3, y0: 0, kx: 200, ky: 0, sigma: 0.05 };
    const pos = i => -L / 2 + (i + 1) * dx;
    const vs = new Float64Array(N * N);
    let vmax = 0;
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) { const v = V(pos(i), -pos(j)); vs[j * N + i] = v; vmax = Math.max(vmax, v); }
    // stable while dt * (largest energy on the grid) < 2: kinetic up to 4/dx^2, plus the highest wall
    const dt = o.dt || Math.min(0.2 * dx * dx, 1 / (4 / (dx * dx) + vmax));
    let re = new Float64Array(N * N), im = new Float64Array(N * N), t = 0;
    const inv = 1 / (2 * dx * dx);
    const H = (f, k, i, j) => {  // (H f) at cell k = (i, j), f = 0 outside the box
      const l = i > 0 ? f[k - 1] : 0, r = i < N - 1 ? f[k + 1] : 0, u = j > 0 ? f[k - N] : 0, d = j < N - 1 ? f[k + N] : 0;
      return -inv * (l + r + u + d - 4 * f[k]) + vs[k] * f[k];
    };
    const reset = () => {
      let s = 0;
      for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
        const x = pos(i), y = -pos(j), k = j * N + i;
        const gss = Math.exp(-((x - p.x0) ** 2 + (y - p.y0) ** 2) / (4 * p.sigma * p.sigma)), ph = p.kx * x + p.ky * y;
        re[k] = gss * Math.cos(ph); im[k] = gss * Math.sin(ph); s += gss * gss;
      }
      s = Math.sqrt(s * dx * dx);
      for (let k = 0; k < N * N; k++) { re[k] /= s; im[k] /= s; }
      // stagger: the imaginary part lives half a step ahead
      const im2 = new Float64Array(N * N);
      for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) { const k = j * N + i; im2[k] = im[k] - (dt / 2) * H(re, k, i, j); }
      im = im2; t = 0;
    };
    const step = () => {
      for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) { const k = j * N + i; re[k] += dt * H(im, k, i, j); }
      for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) { const k = j * N + i; im[k] -= dt * H(re, k, i, j); }
      t += dt;
    };
    reset();
    return { N, L, dx, vs, dt, at(tt) { if (tt < t - dt / 2) reset(); while (t < tt - dt / 2) step(); return { re, im, t }; } };
  };

  /** Draw a 2D simulation into a square canvas at (x, y) with side `size` px: brightness is
   *  probability density, colour is the phase (hue) or one palette colour; walls in ink.
   *  draw(t) updates it for simulated time t. */
  Q.plot2d = (sim, o = {}) => {
    const { x = 660, y = 160, size = 820, phase = true, color = C.accent, gain = 1, walls = true } = o;
    const N = sim.N, cv = document.createElement("canvas");
    cv.width = cv.height = N;
    cv.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:${size}px;height:${size}px;image-rendering:auto;border:4px solid ${C.ink}`;
    document.body.appendChild(cv);
    LV.stage().style.zIndex = 2;
    const g = cv.getContext("2d"), img = g.createImageData(N, N), px = img.data;
    const paper = [251, 249, 241], ink = [34, 34, 34], one = [1, 3, 5].map(i => parseInt(color.slice(i, i + 2), 16));
    const vmax = Math.max(...sim.vs);
    let pTop = 0;
    const hue = (a) => {  // phase -> rgb (a in -pi..pi), a muted wheel that reads on paper
      const h = (a / (2 * Math.PI) + 1) % 1 * 6, c = 0.85, xx = c * (1 - Math.abs(h % 2 - 1));
      const [r, gg, b] = h < 1 ? [c, xx, 0] : h < 2 ? [xx, c, 0] : h < 3 ? [0, c, xx] : h < 4 ? [0, xx, c] : h < 5 ? [xx, 0, c] : [c, 0, xx];
      return [r * 230 + 10, gg * 230 + 10, b * 230 + 10];
    };
    return { canvas: cv, draw(t) {
      const { re, im } = sim.at(t);
      if (!pTop) { for (let k = 0; k < N * N; k++) pTop = Math.max(pTop, re[k] * re[k] + im[k] * im[k]); }
      for (let k = 0; k < N * N; k++) {
        const q = 4 * k;
        if (walls && vmax > 0 && sim.vs[k] > 0.5 * vmax) { px[q] = ink[0]; px[q + 1] = ink[1]; px[q + 2] = ink[2]; px[q + 3] = 255; continue; }
        const d = Math.min(1, Math.sqrt((re[k] * re[k] + im[k] * im[k]) / pTop) * gain);  // sqrt: faint fringes stay visible
        const c = phase ? hue(Math.atan2(im[k], re[k])) : one;
        px[q] = paper[0] + (c[0] - paper[0]) * d; px[q + 1] = paper[1] + (c[1] - paper[1]) * d;
        px[q + 2] = paper[2] + (c[2] - paper[2]) * d; px[q + 3] = 255;
      }
      g.putImageData(img, 0, 0);
    } };
  };

  window.LVQ = Q;
})();
