# disasm/logic/ — game-logic tables (issue #007)

Derived from `rop-original.gen` (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`)
and verified against the code in `disasm/rop.s` plus the emulator harness
(`tools/test_logic_harness.s`). See `docs/logic.md` for the full write-up;
these files are the machine-readable tables behind it.

- `xp_levels.txt` — level thresholds (formula, not a table), max HP / max Power
  per level. Level range is 0–8 (XP 12800+ → level 8).
- `items.txt` — the 20 item categories, table `$D66A3` (10-byte records).
- `price_table.txt` — the 257 price/value records, table `$D6768` (4-byte
  records: [name index][raw value]). Records 1–120 are spells, 186–216 are
  trade goods, food/water and transports.
- `trading_check.txt` — the ringsofpower.co.uk trading guide's 21 goods
  checked against the ROM price table (buy/sell, per good).
- `damage_tests.txt` — the `$3B1EE` damage test vectors and results
  (7 cases, all PASS in the harness).

Regeneration: the tables come from the ROM bytes plus the formulas in
`docs/logic.md`; there is no generator script — re-derive with the
addresses in `docs/logic.md` if the ROM ever changes (it won't).
