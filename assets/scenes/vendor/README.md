# Vendored: matterviz core

`matterviz-core.js` is a browser build (ES module, 375 KB) of the non-Svelte core of
[matterviz](https://github.com/janosh/matterviz) 0.8.0 by Janosh Riebesell, MIT License
(`MATTERVIZ-LICENSE.txt`): structure parsers (CIF, POSCAR, XYZ, PDB, mmCIF, JSON), bond finding,
supercells, lattice planes, element data and colour schemes (VESTA, Jmol), and the binary
phase-diagram builder. `../data/phase-diagrams/*.json` (ten binary diagrams) and
`../data/structures/*` (sample crystal files) come from the same repository.

Rebuilt with esbuild from `src/lib` (entry exports: parse_cif, parse_poscar, parse_xyz,
parse_structure_file, compute_bonds, get_bond_data, BONDING_STRATEGIES, expected_bond_length,
make_supercell, generate_lattice_points, lattice_plane_polygons, clip_frac_plane_to_cell,
ELEMENT_COLOR_SCHEMES, element_by_symbol, build_diagram, parse_curve_ref, find_phase_at_point,
transform_vertices, compute_label_properties, get_phase_color). Rendering for videos is in
`../materials.js`.
