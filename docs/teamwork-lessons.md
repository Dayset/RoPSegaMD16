# Teamwork lessons — the other 20%

The initial flow guide (`CLAUDE.md` + `agent-playbook.md`) got coordination
~80% right: the naming grammar, one task / one shard / one PR, the
`make check` gate, and "decide, don't ask". These are the rules learned
from actual incidents — the ones that prevented the real failure modes.
Each rule names the incident that produced it, so a future agent can see
why it exists instead of treating it as ceremony.

## 1. Diff a branch against main before merging (stale-branch clobber)

Claude force-pushes branches from stale bases. A stale branch's
`auto.csv` **reverts** names (main tier≥1 → branch tier 0), and a merge
of that branch silently un-names work that is already on main.

**Rule:** always diff a branch against current main and count reverts
before merging anything. If the branch reverts any name, do not merge —
ask for a rebase, or regenerate the branch's files on the new tip.

**Incident:** the #60 naming conflict and my own #142 rebase, where
carrying generated files across a main move would have reverted
Claude's #141 names. (See also rule 5.)

## 2. Read the PR number from the tool output

Never assume a PR number. Always read it from the `gh_create_pr.py`
output before calling `gh_merge.py`.

**Incident:** I created PR #134, then merged #133 by guessing the
number. #133 was Claude's docs-only PR and it merged cleanly, so no
harm — but it went in without my trial-merge review.

## 3. Check the merge result BEFORE deleting the branch

A 405 merge failure does not mean the PR is dead; it usually means
GitHub had not finished computing `mergeable` yet (~10 s), or main
moved and both sides touched the same generated files. Wait, re-check
`mergeable` / `mergeable_state`, and retry. **Always read the
`gh_merge.py` result before deleting the branch.**

**Incident:** I deleted `gh-16-shift-steps1-2` after a 405 merge
failure, which closed PR #106 unmerged. The branch's work was
superseded by Claude's #105, but the deletion was premature — the
merge result had not been checked.

## 4. The CRAM precedent (doc-pinned routines get tier 2)

A routine doc-pinned by address with an exact signature/role is named
tier 2 **even with zero callers**. The dead-code skip rule applies only
to routines with no callers **and** no doc coverage.

**Examples:** `pal_get_entry` $0110D0 / $01110A (graphics.md:486–487),
`z80_write_val24_nobus`, `snd_sfx_pointer_12`. All named tier 2 with
no callers, on the strength of a doc citation.

## 5. Push-rebase rules

- The expected-tip argument to `push-rebase.py` **must be the full
  40-char SHA** from `git rev-parse origin/main`. Never fabricate one
  by padding a short SHA — a padded SHA aborts with a misleading
  "tip moved" message (and it happened twice).
- Generated files (`disasm/src/rop.s`, `STATUS.md`, `README.md`,
  `auto.csv`) must be **regenerated on the new parent** before
  rebasing, never carried over. Carrying them across a main move
  reverts the newer main's changes in those files.

**Incident:** my #142 rebase (see rule 1) — the correct sequence was
reset to the new main, re-apply the `auto.csv` edit, re-run `gen_src.py`
+ `status.py`, then push-rebase.

## 6. Git index staleness

`push-via-api.py` reads the working tree and bypasses the git index.
After a push, `git diff` still shows pushed edits. **Always compare
with `git diff origin/main`.** Untracked-but-pushed files show as
"deletions" in `git diff origin/<branch>` — verify branch content with
`git show origin/<branch>:<path>` / `git ls-tree` instead.

## 7. Verify every `git add`

After `git add`, always read `git status --short` and confirm every
intended file is staged. A missing file is silent.

**Incident:** `.gitignore` negation depth — `!patches/*.ips` only
un-ignores one level deep, so `patches/music-off/*.ips` (two levels)
stayed ignored and the first music-off commit shipped the README and
the changed-bytes list but silently dropped the actual `.ips` file.
Fixed with `!patches/**/*.ips` + a repair commit.

## 8. Worktrees live under `~/workspace/rop-work/`, never `/tmp`

`/tmp` is a 512 MB tmpfs, wiped on VM replacement **and** by service
restarts. Never stage uncommitted deliverables only in `/tmp`.

**Incident:** a runtime restart 2026-11-11 ~04:25 EST wiped `/tmp`
and lost the #18 text-pipeline build and the #16 survey. The #18
files were rebuilt from a backup; the #16 survey was re-spawned with
its findings carried in the brief.

## 9. Claude's merge handoff

Claude is shy on merging — he opens PRs but does not merge them (his
auto-mode permission classifier blocks "merge without review"). My
role: review (trial merge + `make check`, diff for stale-branch
reverts per rule 1) and merge. Work for the team or the other coder
goes in a separate GitHub issue — never ask Dayset to relay it.

## 10. Naming collisions from parallel work

Two agents can name the same routine in parallel. Before pushing a
naming batch, re-check the tip and the `auto.csv` rows for your
addresses. If Claude names one of your addresses first, his name
stands (or the better name wins on evidence) — drop yours, and close
your PR as superseded with an explanatory comment rather than
force-merging over it.

**Incidents:** 0x012F48 (my `sys_poll_menu_input` vs his
`pad_poll_queued_12f48`, PR #142 closed as superseded), 0x03AAC4 (my
`combat_noop_stub` vs his `sys_stub_03aac4`), 0x039DF4 (my undecided
phased spell-step effect vs his `spell_apply_actor_39df4`).

## 11. Dispatch targets are labelled, not named

Computed-dispatch case bodies (mid-routine `jmp *+2(pc,d0.w)` targets)
get `gen_src` labels, not `auto.csv` routine names. Naming one as a
routine is a factual error — it has no prologue, shares the caller's
frame, and exits via the caller's epilogue; it is not callable.

**Precedent:** the $00DF58 jump-table handlers (112 handlers carved as
code, 114 targets labelled, none given routine names). The 7 remaining
tier-0 rows in `auto.csv` are all dispatch cases, identified in their
notes; the honest end state is 446/446 routines named, 7 cases
identified, 0 genuinely-unknown rows.

## 12. The "help Claude finish" directive

Dayset, 2026-11-11 03:11 EST: "help claude finish". I actively help
Claude's line, superseding the earlier stay-out-of-his-line stance.
That means reviewing and merging his PRs (rule 9), and doing the
naming/identification work he leaves open — but it does not mean
re-doing his line's tasks or second-guessing his names without
evidence.
