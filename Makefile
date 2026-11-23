# Makefile — issue #5: make targets and the pre-push rebuild gate.
# Needs: vasm in tools/vasm (make vasm), python3, and rop-original.gen (never committed).
ROM      := rop-original.gen
REBUILT  := build/rop-rebuilt.gen
PY       := python3
SIZE     ?= 1m

.PHONY: help vasm build verify coverage regions gate rom-free lint check status clean assets shift-test playtest roundtrip

help:
	@echo "make vasm      install pinned assembler into tools/vasm"
	@echo "make build     assemble disasm/src/rop.s -> $(REBUILT)"
	@echo "make verify    byte-compare rebuilt ROM with $(ROM) (fails on any difference)"
	@echo "make coverage  coverage meter for disasm/src/rop.s"
	@echo "make regions   ROM data-region inventory"
	@echo "make assets    rebuild the DD5C asset records from assets/gfx/ -> build/assets.gen"
	@echo "make roundtrip extract -> re-pack -> byte-identical, per class (lzss, text, assets, song)"
	@echo "make gate      build + verify + coverage (run before every push touching disasm/src or tools/)"
	@echo "make rom      build a feature ROM: make rom FEATURES=music-off"
	@echo "              (FEATURES= empty builds the byte-identical base)"
	@echo "              make rom SIZE=2m builds the 2 MB container"
	@echo "              (1 MB base + second megabyte for tile data, #252)"
	@echo "make rom-free  fail if any ROM image (*.gen) is tracked by git"
	@echo "make clean     remove build/"
	@echo "make playtest  deterministic playtest table (issue #240): input-replay overlay + frozen routes on original, flat-zoomed, walk-unused-frames; reuses cached traces in .scratch-smooth240"

vasm:
	sh tools/install_vasm.sh

build:
	sh tools/build.sh

verify: build
	$(PY) tools/verify_rebuild.py $(REBUILT) $(ROM)

coverage:
	$(PY) tools/coverage_rop.py disasm/src/rop.s --md

regions:
	$(PY) tools/regions_inventory.py disasm/src/rop.s --md

assets:
	$(PY) tools/build_assets.py

roundtrip:
	$(PY) tools/roundtrip.py

gate: verify coverage

rom-free:
	@if git ls-files | grep -q "\.gen$$"; then echo "ROM image tracked by git:"; git ls-files | grep "\.gen$$"; exit 1; else echo "PASS no tracked ROM images"; fi

lint:
	python3 tools/lint_symbols.py

check: lint gate rom-free
	@python3 tools/ram_writecheck.py
	@python3 tools/status.py

status:
	@python3 tools/status.py

shift-test:
	sh tools/shift_test.sh

setup:
	sh tools/setup.sh

rom:
	$(PY) tools/build_rom.py FEATURES=$(FEATURES) --size $(SIZE)

boot:
	sh tools/test_harness.sh

unit:
	@for t in tools/tests/test_*.py; do python3 "$$t" || exit 1; done

# Deterministic playtest harness (issue #240). The table uses the
# three frozen ROMs with the input-replay overlay applied as a
# test-only overlay (the overlay is never part of a shipped ROM).
# Wiring FEATURES= (the #239 feature build) into the table is a
# follow-up. Traces are cached in .scratch-smooth240/ and reused
# when the overlay ROM + route are unchanged; delete the
# *.trace.json to force a re-run. Each trace is ~100 s wall
# (emulator runs at real-time 60 fps).
playtest:
	python3 tools/playtest_metrics.py table

clean:
	rm -rf build
