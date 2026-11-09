# Disassembly

Generated output lives here. Do not hand-edit generated files — edit the
sources / scripts in `tools/` and regenerate, so the disassembly stays
reproducible.

- `rop.s` — first-pass linear disassembly (issue #002, done). 20 MB, so it is
  generated locally and NOT committed to GitHub — regenerate it with
  `tools/.venv/bin/python tools/disassemble.py` (needs your own ROM dump as
  `rop-original.gen`; output is byte-identical on re-run).
- `map.md` — code / text / graphics / unknown address map
- `text/` — extracted strings with offsets (issue #004)
