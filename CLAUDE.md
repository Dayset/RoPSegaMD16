# Working rules for agent sessions

Rings of Power (Mega Drive, 1992) disassembly. **Goal: finish the full
disassembly.** Order of work: M5 (clean rebuild) → M11 (names) → M8 (all
bytes accounted) → M9 (shiftable) → M10 (asset round-trip). Everything else
is parked unless Dayset assigns it by name.

Task queue and method: `docs/agent-playbook.md`. Read it once per session.

## 1. Decide, don't ask

You never stop to ask about any of these. Pick the default, record it, go on.

| Situation | Default |
|---|---|
| What to name something | Apply the grammar in §3. Any legal name beats `FUN_`. |
| Two plausible names | Take the more general one, tier `1`. |
| Not sure what a routine does after 20 min | Name it `<subsys>_unk_<addr>`, tier `0`, one-line note, next. |
| Not sure what a data region is after 20 min | Class `unknown`, note what you ruled out, next. |
| Which task to take | Top unclaimed card in the playbook queue. |
| Task turns out bigger than the card | Finish the part that passes `make check`, PR it, write the rest as a new card. |
| A finding contradicts a doc | Record both with evidence in the doc. Do not resolve it now. |
| Interesting game-mechanics lead | One line in `docs/leads.md`. Do not chase it. |
| File layout, script name, CSV column order, commit wording | Your call. Follow the nearest existing example. |

**Only four things go to Dayset**, and none of them block other work:
1. Choosing what a mod/patch should change in the game.
2. Replacing the assembler, emulator or disassembler.
3. Deleting a branch or file that holds work you cannot prove is on `main`.
4. Anything about distributing ROM bytes.

Write these in `docs/questions.md` as: question, the default you took,
what changes if the answer is different. Then keep working on the default.
A session that ends with a question and no merged PR has failed.

## 2. One task, one shard, one PR

- A task card names the files you may edit. Stay inside them. Two agents
  never hold the same shard.
- Branch `gh-<N>-short-name` off fresh `main`. Rebase before merge. Merge
  in the same session. A branch older than 24 h is a defect: land it or
  close it.
- `disasm/src/rop.s` is generated. Never edit it. Your output is data:
  rows in `disasm/symbols/*.csv` and `disasm/regions.csv`, or a change to
  a generator in `tools/`.
- PR body = the card's acceptance lines, each `met` or `not met` + the
  `make check` summary line. Nothing else is required.

## 3. Naming grammar (no discussion needed)

- Code: `<subsys>_<verb>_<object>`, lower snake case, ≤ 32 chars.
- Subsystems (closed list): `boot sys mem math rng vdp gfx pal pad snd z80
  sram save text dict lzss map world npc shop combat spell inv menu ui time`.
  Nothing fits → `sys`.
- Data: `tbl_ ptr_ str_ gfx_ pal_ map_ snd_` + object. RAM: `ram_<subsys>_<thing>`.
- Name taken → append the address: `menu_draw_box_1f296`.
- Tier column, always filled:
  - `0` structural only (subsystem known, role not)
  - `1` role read from the code (static)
  - `2` role confirmed by a doc citation or a live trace
- Existing names are kept. Rename only when a name is proven **wrong**,
  never because another is nicer.

## 4. Evidence: how much is enough

- Naming and region classing: static evidence is enough (address + what
  the code touches). Do not build a harness to name a routine.
- Live verification (BlastEm harness) is required only for: a patch that
  changes bytes, or a game-mechanics number stated as fact in `docs/`.
- Any claim: address + bytes. Disagreements are kept side by side.

## 5. The gate

`make check` before every push. It runs: build → byte-identical verify →
symbol lint → regenerate `STATUS.md`. If it fails, you do not push.
Code paths changed → also `tools/test_harness.sh`.

## 6. Status is generated, never typed

`tools/status.py` writes `STATUS.md` and the README block between the
`<!-- status -->` markers. Do not hand-edit progress numbers, bars, hashes
or boards anywhere. GitHub issues + milestones are the only tracker.
`PROGRESS.md` and `issues/` are frozen archives.

Session log: `docs/log/YYYY-MM-DD.md`, five lines maximum per task: card,
what moved (metric before → after), what is left, leads, questions.

## 7. Facts about the toolchain

- Assembler is **vasm**, Motorola syntax: hex is `$1234`. `0x1234`
  assembles to the wrong length.
- ROM is never committed. `rop-original.gen`, MD5
  `30c18fdbe2183f64702ae9f1a45d63f9`.
- After a byte change: `tools/checksum.py fix-all` (runtime checksum at
  `$FD098` first, header `$18E` last).
- An instruction vasm re-encodes stays a `dc.w` fallback with a `; was:`
  comment until the generator handles its class.
