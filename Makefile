# Makefile — issue #5: make targets and the pre-push rebuild gate.
# Needs: vasm in tools/vasm (make vasm), python3, and rop-original.gen (never committed).
ROM      := rop-original.gen
REBUILT  := build/rop-rebuilt.gen
PY       := python3

.PHONY: help vasm build verify coverage regions gate rom-free lint check status clean assets shift-test

help:
	@echo "make vasm      install pinned assembler into tools/vasm"
	@echo "make build     assemble disasm/src/rop.s -> $(REBUILT)"
	@echo "make verify    byte-compare rebuilt ROM with $(ROM) (fails on any difference)"
	@echo "make coverage  coverage meter for disasm/src/rop.s"
	@echo "make regions   ROM data-region inventory"
	@echo "make assets    rebuild the DD5C asset records from assets/gfx/ -> build/assets.gen"
	@echo "make gate      build + verify + coverage (run before every push touching disasm/src or tools/)"
	@echo "make rom-free  fail if any ROM image (*.gen) is tracked by git"
	@echo "make clean     remove build/"

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

gate: verify coverage

rom-free:
	@if git ls-files | grep -q "\.gen$$"; then echo "ROM image tracked by git:"; git ls-files | grep "\.gen$$"; exit 1; else echo "PASS no tracked ROM images"; fi

lint:
	python3 tools/lint_symbols.py

check: lint gate rom-free
	@python3 tools/status.py

status:
	@python3 tools/status.py

shift-test:
	sh tools/shift_test.sh

setup:
	sh tools/setup.sh

rom: build

boot:
	sh tools/test_harness.sh

unit:
	@for t in tools/tests/test_*.py; do python3 "$$t" || exit 1; done

clean:
	rm -rf build
