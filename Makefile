# Makefile — issue #5: make targets and the pre-push rebuild gate.
# Needs: vasm in tools/vasm (make vasm), python3, and rop-original.gen (never committed).
ROM      := rop-original.gen
REBUILT  := build/rop-rebuilt.gen
PY       := python3

.PHONY: help vasm build verify coverage regions gate rom-free check status clean

help:
	@echo "make vasm      install pinned assembler into tools/vasm"
	@echo "make build     assemble disasm/src/rop.s -> $(REBUILT)"
	@echo "make verify    byte-compare rebuilt ROM with $(ROM) (fails on any difference)"
	@echo "make coverage  coverage meter for disasm/src/rop.s"
	@echo "make regions   ROM data-region inventory"
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

gate: verify coverage

rom-free:
	@if git ls-files | grep -q "\.gen$$"; then echo "ROM image tracked by git:"; git ls-files | grep "\.gen$$"; exit 1; else echo "PASS no tracked ROM images"; fi

check: gate rom-free
	@python3 tools/status.py

status:
	@python3 tools/status.py

clean:
	rm -rf build
