/* materials.js - materials-science parts for scenes (references/scenes.md §5). Load after lv.js and
 * blocks.js. Global LVM. Built on matterviz (MIT, github.com/janosh/matterviz): its core is
 * vendored as /kit/vendor/matterviz-core.js (parsers, bonds, supercells, lattice planes, element
 * colours and radii, binary phase diagrams), and its data as /kit/data/. Drawing is done here,
 * from time t only, so every frame is exact.
 *
 *   LVM.ready.then(async () => {
 *     const pd = LVM.phaseDiagram(svg, await LVM.phaseData("Pb-Sn"), { x: 160, y: 140, width: 900, height: 760 });
 *     LV.frame(t => pd.show(0.4, 600 - 60 * LV.progress(1, t)));   // a cooling path at 40% Sn
 *     LV.beat(b => b.hold(4000));
 *     LV.done();
 *   });
 *
 * Parts: phaseData · phaseDiagram (regions, boundaries, tie line, lever rule) · microstructure ·
 *        cell (sc, bcc, fcc, hcp, diamond, nacl, cscl) · structureFile · crystal3d (atoms, bonds,
 *        unit cell, supercell, lattice planes) · edgeDislocation (glide, Burgers circuit)
 */
(function () {
  const { C, el, text, tint } = LV;
  const M = {};
  M.ready = import("/kit/vendor/matterviz-core.js").then(core => (M.core = core));
  const getText = url => fetch(url).then(r => { if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.text(); });

  /** A binary phase diagram from the bundled set (Pb-Sn, Cu-Zn, Fe-Fe3C, Al-Cu, Al-Si, Al-Mg, Al-Fe,
   *  Au-Sn, Fe-Ni, A-B) or a JSON file next to the scene (same format: curves + regions). */
  M.phaseData = name => getText(name.endsWith(".json") ? name : `/kit/data/phase-diagrams/${name}.json`).then(JSON.parse);
  /** A crystal from a file (CIF, POSCAR, XYZ, PDB, mmCIF, pymatgen JSON): bundled samples are
   *  /kit/data/structures/{NaCl-cubic.poscar, BaTiO3-tetragonal.poscar, TiO2.cif, LiFePO4.cif, Si-diamond.mmcif}. */
  M.structureFile = url => getText(url).then(t => M.core.parse_structure_file(t, url.split("/").pop()));

  // ------------------------------------------------------------------ phase diagrams
  const isLiquid = n => /^l$|liquid/i.test(n.trim());
  const solidColours = [C.grn, C.gold, C.accent, C.blu, "#6B4C9A"];
  /** Lecture colours: liquid blue, each single solid phase its own colour, two-phase regions pale. */
  function regionColours(regions) {
    const singles = regions.filter(r => !r.name.includes("+") && !isLiquid(r.name)).map(r => r.name);
    return r => {
      if (isLiquid(r.name)) return tint(C.blu, 22);
      if (r.name.includes("+")) return tint(C.mute, 10);
      return tint(solidColours[singles.indexOf(r.name) % solidColours.length], 26);
    };
  }
  const centroid = vs => {  // area-weighted polygon centroid
    let a = 0, cx = 0, cy = 0;
    for (let i = 0; i < vs.length; i++) { const [x1, y1] = vs[i], [x2, y2] = vs[(i + 1) % vs.length], k = x1 * y2 - x2 * y1;
      a += k; cx += (x1 + x2) * k; cy += (y1 + y2) * k; }
    return Math.abs(a) < 1e-12 ? vs[0] : [cx / (3 * a), cy / (3 * a)];
  };

  /** Draw a binary phase diagram. opts: x, y, width, height, colors ("lecture" | "matterviz"),
   *  labels (region names), unit ("%" composition labels). Returns
   *  { X(c), Y(T), data, at(c, T) -> region, tie(c, T) -> {cL, cR, left, right, fL, fR} | null,
   *    show(c, T, {tie, readout}) -> places the state point, tie line and lever-rule readout }. */
  M.phaseDiagram = (parent, input, o = {}) => {
    const d = M.core.build_diagram(input);
    const { x = 160, y = 140, width = 900, height = 760, colors = "lecture", labels = true, size = 30 } = o;
    const [T0, T1] = d.temperature_range, unit = d.temperature_unit || "K", [A, B] = d.components;
    const X = c => x + c * width, Y = T => y + height - (T - T0) / (T1 - T0) * height;
    const g = el("g", {}, parent);
    const colour = colors === "matterviz" ? (r => r.color || C.light) : regionColours(d.regions);
    const pts = vs => vs.map(([c, T]) => `${X(c).toFixed(1)},${Y(T).toFixed(1)}`).join(" ");
    for (const r of d.regions) el("polygon", { points: pts(r.vertices), fill: colour(r), stroke: "none" }, g);
    for (const b of d.boundaries) el("polyline", { points: pts(b.points), fill: "none", stroke: C.ink,
      "stroke-width": b.type === "eutectic" || b.type === "peritectic" ? 3 : 3.5, "stroke-linejoin": "round" }, g);
    el("rect", { x, y, width, height, fill: "none", stroke: C.ink, "stroke-width": 2.5 }, g);
    // axes: composition of B in %, temperature in steps of 50 or 100
    for (let k = 0; k <= 10; k += 2) {
      el("line", { x1: X(k / 10), y1: y + height, x2: X(k / 10), y2: y + height + 10, stroke: C.ink, "stroke-width": 2 }, g);
      text(g, X(k / 10), y + height + 44, `${k * 10}`, { "text-anchor": "middle", "font-size": size, fill: C.mute });
    }
    text(g, x + width / 2, y + height + 92, `${d.composition_unit || "mol%"} ${B}`, { "text-anchor": "middle", "font-size": size + 2, fill: C.ink });
    text(g, x, y + height + 92, A, { "text-anchor": "middle", "font-size": size + 4, fill: C.ink, "font-weight": "bold" });
    text(g, x + width, y + height + 92, B, { "text-anchor": "middle", "font-size": size + 4, fill: C.ink, "font-weight": "bold" });
    const step = (T1 - T0) > 600 ? 200 : (T1 - T0) > 250 ? 100 : 50;
    for (let T = Math.ceil(T0 / step) * step; T <= T1; T += step) {
      el("line", { x1: x - 10, y1: Y(T), x2: x, y2: Y(T), stroke: C.ink, "stroke-width": 2 }, g);
      text(g, x - 16, Y(T) + size / 3, `${T}`, { "text-anchor": "end", "font-size": size, fill: C.mute });
    }
    text(g, x - 16, y - 18, `T (${unit === "C" ? "°C" : unit})`, { "text-anchor": "end", "font-size": size, fill: C.ink });
    if (labels) for (const r of d.regions) {  // narrow regions are labelled outside the frame, with a leader
      const [c, T] = r.label_position || centroid(r.vertices);
      const cs = r.vertices.map(v => v[0]), wide = (Math.max(...cs) - Math.min(...cs)) * width;
      const lbl = text(g, X(c), Y(T) + size / 3, r.name, { "text-anchor": "middle", "font-size": size, fill: C.ink, serif: true });
      if (lbl.getComputedTextLength() + 16 > wide) {
        const left = c < 0.5, lx = left ? x - 20 : x + width + 20;
        lbl.setAttribute("x", left ? x - 26 : x + width + 26); lbl.setAttribute("text-anchor", left ? "end" : "start");
        el("line", { x1: X(c), y1: Y(T), x2: lx, y2: Y(T), stroke: C.mute, "stroke-width": 1.5 }, g);
      }
    }
    for (const p of d.special_points || []) {
      el("circle", { cx: X(p.position[0]), cy: Y(p.position[1]), r: 7, fill: C.ink }, g);
      if (p.label) text(g, X(p.position[0]) + 12, Y(p.position[1]) - 12, p.label, { "font-size": size, fill: C.ink, serif: true });
    }
    // the state point, tie line and readout (placed by show)
    const tieG = el("g", {}, g);
    const tieLine = el("line", { stroke: C.gold, "stroke-width": 5 }, tieG);
    const ends = [0, 1].map(() => el("circle", { r: 9, fill: C.gold, stroke: C.ink, "stroke-width": 2 }, tieG));
    const dot = el("circle", { r: 13, fill: C.accent, stroke: "white", "stroke-width": 3 }, g);
    const read = el("g", {}, parent);
    const lines = [0, 1, 2].map(k => text(read, (o.readout || [x + width + 50, y + 60])[0], (o.readout || [x + width + 50, y + 60])[1] + k * 52, "",
      { "font-size": size + 8, fill: k ? C.ink : C.accent }));
    const at = (c, T) => M.core.find_phase_at_point(c, T, d);
    const tie = (c, T) => {
      const r = at(c, T);
      if (!r || !r.name.includes("+")) return null;
      const xs = [];
      const vs = r.vertices;
      for (let i = 0; i < vs.length; i++) {
        const [c1, t1] = vs[i], [c2, t2] = vs[(i + 1) % vs.length];
        if ((t1 - T) * (t2 - T) <= 0 && t1 !== t2) xs.push(c1 + (T - t1) / (t2 - t1) * (c2 - c1));
      }
      const cL = Math.max(...xs.filter(v => v <= c + 1e-9)), cR = Math.min(...xs.filter(v => v >= c - 1e-9));
      if (!isFinite(cL) || !isFinite(cR) || cR - cL < 1e-6) return null;
      const name = (cc, side) => (at(Math.min(1, Math.max(0, cc + side * 0.004)), T) || {}).name || "";
      const fR = (c - cL) / (cR - cL);
      return { cL, cR, left: name(cL, -1), right: name(cR, 1), fL: 1 - fR, fR };
    };
    const show = (c, T, { tie: showTie = true, readout = true } = {}) => {
      dot.setAttribute("cx", X(c)); dot.setAttribute("cy", Y(T));
      const tl = showTie ? tie(c, T) : null;
      tieG.setAttribute("visibility", tl ? "visible" : "hidden");
      if (tl) {
        tieLine.setAttribute("x1", X(tl.cL)); tieLine.setAttribute("x2", X(tl.cR));
        tieLine.setAttribute("y1", Y(T)); tieLine.setAttribute("y2", Y(T));
        ends[0].setAttribute("cx", X(tl.cL)); ends[1].setAttribute("cx", X(tl.cR));
        ends.forEach(e => e.setAttribute("cy", Y(T)));
      }
      const r = at(c, T);
      lines[0].textContent = readout ? `${Math.round(T)} ${unit === "C" ? "°C" : unit}: ${r ? r.name : ""}` : "";
      lines[1].textContent = readout && tl ? `${tl.left}: ${(100 * tl.fL).toFixed(0)}%` : "";
      lines[2].textContent = readout && tl ? `${tl.right}: ${(100 * tl.fR).toFixed(0)}%` : "";
      return { region: r, tie: tl };
    };
    return { g, X, Y, data: d, at, tie, show, colour };
  };

  /** A microscope view: grains of a solid phase growing in a matrix as the solid fraction rises.
   *  set(fSolid, {solid, matrix}) redraws for fraction fSolid (0..1) with the two colours. */
  M.microstructure = (parent, o = {}) => {
    const { x = 1420, y = 560, r = 230, grains = 22, seed = 7 } = o;
    const id = "lvmic" + Math.random().toString(36).slice(2, 7);
    el("circle", { cx: x, cy: y, r }, el("clipPath", { id }, LV.stage().querySelector("defs")));
    const g = el("g", { "clip-path": `url(#${id})` }, parent);
    const bg = el("rect", { x: x - r, y: y - r, width: 2 * r, height: 2 * r }, g);
    let s = seed; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
    const centres = [...Array(grains)].map(() => [x - r + 2 * r * rnd(), y - r + 2 * r * rnd(), 0.6 + 0.8 * rnd()]);
    const blobs = centres.map(() => el("circle", { "stroke-width": 2 }, g));
    el("circle", { cx: x, cy: y, r, fill: "none", stroke: C.ink, "stroke-width": 5 }, parent);
    return { set(f, { solid = C.grn, matrix = C.blu } = {}) {
      bg.setAttribute("fill", tint(matrix, 30));
      const rr = Math.sqrt(Math.max(0, f) * 4 * r * r / (Math.PI * grains)) * 1.15;  // area ~ f of the view
      blobs.forEach((b, i) => { b.setAttribute("cx", centres[i][0]); b.setAttribute("cy", centres[i][1]);
        b.setAttribute("r", Math.max(0, rr * centres[i][2])); b.setAttribute("fill", tint(solid, 55)); b.setAttribute("stroke", solid); });
    } };
  };

  // ----------------------------------------------------------------- crystals (3D)
  /** A conventional unit cell as a structure (matterviz format): kind sc | bcc | fcc | hcp | diamond |
   *  nacl | cscl; a in angstrom; elements [A] or [A, B]. */
  M.cell = (kind, { a = 3.6, elements = ["Cu"], c = null } = {}) => {
    const [A, B = A] = elements;
    const frac = {
      sc: [[A, 0, 0, 0]], bcc: [[A, 0, 0, 0], [A, 0.5, 0.5, 0.5]],
      fcc: [[A, 0, 0, 0], [A, 0.5, 0.5, 0], [A, 0.5, 0, 0.5], [A, 0, 0.5, 0.5]],
      diamond: [[A, 0, 0, 0], [A, 0.5, 0.5, 0], [A, 0.5, 0, 0.5], [A, 0, 0.5, 0.5], [A, 0.25, 0.25, 0.25], [A, 0.75, 0.75, 0.25], [A, 0.75, 0.25, 0.75], [A, 0.25, 0.75, 0.75]],
      nacl: [[A, 0, 0, 0], [A, 0.5, 0.5, 0], [A, 0.5, 0, 0.5], [A, 0, 0.5, 0.5], [B, 0.5, 0, 0], [B, 0, 0.5, 0], [B, 0, 0, 0.5], [B, 0.5, 0.5, 0.5]],
      cscl: [[A, 0, 0, 0], [B, 0.5, 0.5, 0.5]],
      hcp: [[A, 1 / 3, 2 / 3, 0.25], [A, 2 / 3, 1 / 3, 0.75]],
    }[kind];
    if (!frac) throw new Error(`LVM.cell: unknown kind ${kind}`);
    const cc = c || (kind === "hcp" ? 1.633 * a : a);
    const matrix = kind === "hcp" ? [[a, 0, 0], [-a / 2, a * Math.sqrt(3) / 2, 0], [0, 0, cc]] : [[a, 0, 0], [0, a, 0], [0, 0, a]];
    const xyz = f => [0, 1, 2].map(k => f[0] * matrix[0][k] + f[1] * matrix[1][k] + f[2] * matrix[2][k]);
    return { lattice: { matrix, a, b: a, c: cc, pbc: [true, true, true] },
             sites: frac.map(([e, ...f], i) => ({ species: [{ element: e, occu: 1, oxidation_state: 0 }], abc: f, xyz: xyz(f), label: `${e}${i + 1}`, properties: {} })) };
  };

  /** Draw a crystal with three.js: atoms (VESTA colours, radius `scale` x atomic radius), bonds,
   *  unit-cell edges, optional supercell [na, nb, nc] and lattice planes [{hkl, color}].
   *  images: also draw the atoms on the cell's faces, edges and corners (the textbook picture).
   *  Returns { group (centred on the cell), atoms, bonds, planes, centre, size }. */
  M.crystal3d = (THREE, structure, o = {}) => {
    const { scale = 0.42, bonds = false, cell = true, supercell = null, planes = [], images = true,
            scheme = "Vesta", maxBond = 3.2, colors = {} } = o;
    const core = M.core;
    const s = supercell ? core.make_supercell(structure, supercell) : structure;
    const L = s.lattice.matrix, cart = f => [0, 1, 2].map(k => f[0] * L[0][k] + f[1] * L[1][k] + f[2] * L[2][k]);
    const group = new THREE.Group();
    const palette = core.ELEMENT_COLOR_SCHEMES[scheme] || core.ELEMENT_COLOR_SCHEMES.Vesta;
    const sites = [];
    for (const site of s.sites) {
      const e = site.species[0].element, f = site.abc.map(v => ((v % 1) + 1) % 1);
      const shifts = images ? [0, 1].flatMap(i => [0, 1].flatMap(j => [0, 1].map(k => [i, j, k]))) : [[0, 0, 0]];
      for (const sh of shifts) {
        const ff = f.map((v, k) => v + sh[k]);
        if (sh.some((v, k) => v === 1 && f[k] > 1e-6)) continue;   // only images of atoms on faces/edges/corners
        sites.push({ e, xyz: cart(ff) });
      }
    }
    const geoms = {}, mats = {};
    const atoms = sites.map(({ e, xyz }) => {
      const el_ = core.element_by_symbol.get(e) || {}, rad = (el_.atomic_radius || el_.covalent_radius || 1.4) * scale;
      const key = `${e}`;
      geoms[key] = geoms[key] || new THREE.SphereGeometry(rad, 40, 28);
      mats[key] = mats[key] || new THREE.MeshStandardMaterial({ color: colors[e] || palette[e] || "#aaaaaa", roughness: 0.4, metalness: 0.05 });
      const m = new THREE.Mesh(geoms[key], mats[key]); m.position.set(...xyz); m.userData.element = e; group.add(m); return m;
    });
    const bondMeshes = [];
    if (bonds) {
      const bmat = new THREE.MeshStandardMaterial({ color: 0x9a9a9a, roughness: 0.5 });
      for (let i = 0; i < sites.length; i++) for (let j = i + 1; j < sites.length; j++) {
        const a = new THREE.Vector3(...sites[i].xyz), b = new THREE.Vector3(...sites[j].xyz), dlen = a.distanceTo(b);
        if (dlen > maxBond || sites[i].e === sites[j].e && bonds !== "all") continue;
        const cyl = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, dlen, 16), bmat);
        cyl.position.copy(a.clone().add(b).multiplyScalar(0.5));
        cyl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
        group.add(cyl); bondMeshes.push(cyl);
      }
    }
    if (cell) {
      const n = supercell || [1, 1, 1], pts = [];
      const E = [[0, 0, 0, 1, 0, 0], [0, 1, 0, 1, 1, 0], [0, 0, 1, 1, 0, 1], [0, 1, 1, 1, 1, 1], [0, 0, 0, 0, 1, 0], [1, 0, 0, 1, 1, 0],
                 [0, 0, 1, 0, 1, 1], [1, 0, 1, 1, 1, 1], [0, 0, 0, 0, 0, 1], [1, 0, 0, 1, 0, 1], [0, 1, 0, 0, 1, 1], [1, 1, 0, 1, 1, 1]];
      const Lu = structure.lattice.matrix, cu = f => [0, 1, 2].map(k => f[0] * Lu[0][k] + f[1] * Lu[1][k] + f[2] * Lu[2][k]);
      for (let i = 0; i < n[0]; i++) for (let j = 0; j < n[1]; j++) for (let k = 0; k < n[2]; k++)
        for (const e of E) pts.push(...cu([e[0] + i, e[1] + j, e[2] + k]), ...cu([e[3] + i, e[4] + j, e[5] + k]));
      const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
      group.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: 0x222222 })));
    }
    const planeMeshes = planes.map(({ hkl, color = C.accent, opacity = 0.45 }) => {
      const pg = new THREE.Group();
      for (const { polygon } of core.lattice_plane_polygons({ hkl }, structure.lattice.matrix)) {
        const v = []; for (let i = 1; i < polygon.length - 1; i++) v.push(...polygon[0], ...polygon[i], ...polygon[i + 1]);
        const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
        pg.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false })));
      }
      group.add(pg); return pg;
    });
    const box = new THREE.Box3().setFromObject(group), centre = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
    group.children.forEach(ch => ch.position.sub(centre));
    return { group, atoms, bonds: bondMeshes, planes: planeMeshes, centre, size: Math.max(size.x, size.y, size.z) };
  };

  // ----------------------------------------------------------------- dislocations (2D)
  /** A square lattice with an edge dislocation on the middle slip plane (the extra half plane is
   *  above it). draw(core) puts the core at column `core` (it glides as core grows; the slipped
   *  region is left of it: the top half has moved one Burgers vector). circuit(i0, j0, w, h)
   *  draws a Burgers circuit of w x h atom steps and returns the closure-failure arrow. */
  M.edgeDislocation = (parent, o = {}) => {
    const { x = 200, y = 220, cols = 16, rows = 8, sp = 90, r = 15, width = 1.1 } = o;
    const g = el("g", {}, parent);
    const half = rows / 2;
    el("line", { x1: x - sp, y1: y + (half - 0.5) * sp, x2: x + cols * sp, y2: y + (half - 0.5) * sp,
                 stroke: C.accent, "stroke-width": 3, "stroke-dasharray": "14 10" }, g);
    text(g, x + cols * sp - 10, y + (half - 0.5) * sp - 14, "slip plane", { "text-anchor": "end", "font-size": 32, fill: C.accent });
    const atoms = [];
    for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++)
      atoms.push({ i, j, node: el("circle", { r, fill: tint(C.blu, 55), stroke: C.ink, "stroke-width": 2 }, g) });
    const perp = text(g, 0, 0, "⊥", { "text-anchor": "middle", "font-size": 64, fill: C.accent, "font-weight": "bold" });
    const sig = v => 1 / (1 + Math.exp(-Math.max(-9, Math.min(9, v))));
    const pos = (i, j, core) => {  // upper rows (j < half) are shifted right by sig((core - i)/width)
      const up = j < half, sx = up ? sig((core - i) / width) : 0;
      const bump = (up ? -1 : 1) * 0.12 * Math.exp(-((i + sx - core) ** 2) / 3);
      return [x + (i + sx) * sp, y + (j + bump) * sp];
    };
    let current = 0;
    const draw = core => {
      current = core;
      for (const a of atoms) { const [px, py] = pos(a.i, a.j, core); a.node.setAttribute("cx", px); a.node.setAttribute("cy", py); }
      const vis = core > -0.5 && core < cols - 0.5;
      perp.setAttribute("visibility", vis ? "visible" : "hidden");
      perp.setAttribute("x", x + core * sp + 0.5 * sp); perp.setAttribute("y", y + (half - 0.5) * sp + 22);
    };
    const circ = el("polyline", { fill: "none", stroke: C.gold, "stroke-width": 6, "stroke-linejoin": "round" }, g);
    const gap = LVB.arrow(g, { color: C.accent, width: 6, head: 20 });
    /** Burgers circuit around the core, walked atom to atom: from the bottom-left atom (i0, j0 + h)
     *  h steps up, w right, h down, w left. Up and down steps go to the atom directly above or below,
     *  so a circuit that encloses the dislocation does not close: the gap is the Burgers vector b.
     *  frac (0..1) draws part of it, for drawing it on. */
    const circuit = (i0, j0, w, h, frac = 1) => {
      const xOf = (i, j) => pos(i, j, current)[0];
      const nearest = (j, xx) => { let best = 0, bd = 1e9; for (let i = -2; i < cols + 2; i++) { const dd = Math.abs(xOf(i, j) - xx); if (dd < bd) { bd = dd; best = i; } } return best; };
      let i = i0, j = j0 + h;
      const path = [[i, j]];
      for (let k = 0; k < h; k++) { const xx = xOf(i, j); j -= 1; i = nearest(j, xx); path.push([i, j]); }
      for (let k = 0; k < w; k++) { i += 1; path.push([i, j]); }
      for (let k = 0; k < h; k++) { const xx = xOf(i, j); j += 1; i = nearest(j, xx); path.push([i, j]); }
      for (let k = 0; k < w; k++) { i -= 1; path.push([i, j]); }
      if (frac <= 0) { circ.setAttribute("points", ""); gap.set(0, 0, 0, 0); return { start: [0, 0], end: [0, 0], closed: true }; }
      const n = Math.max(1, Math.round(frac * (path.length - 1)));
      const P = path.slice(0, n + 1).map(([a, b]) => pos(a, b, current));
      circ.setAttribute("points", P.map(p => p.join(",")).join(" "));
      const startP = P[0], endP = P[P.length - 1];
      if (frac >= 1 && Math.hypot(endP[0] - startP[0], endP[1] - startP[1]) > 4) gap.set(endP[0], endP[1], startP[0], startP[1]);
      else gap.set(0, 0, 0, 0);
      return { start: startP, end: endP, closed: Math.hypot(endP[0] - startP[0], endP[1] - startP[1]) < 4 };
    };
    draw(-2);
    return { g, draw, circuit, pos };
  };

  window.LVM = M;
})();
