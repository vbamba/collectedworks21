# Backlog — collectedworks21 / splitter

Deferred work items with enough context to pick up cold in a new session.
Splitter repo lives at `~/Projects/collectedworks` (sibling). Serving repo is
this one. Conda envs: splitter = `faiss_env`, serving = `collectedworks_env`.

---

## STATUS UPDATE (2026-06-25) — B + B1 done, C deferred (regression found)

A full corpus rebuild shipped **B1** and **B** locally (not yet deployed — held
for review). **C was attempted twice and reverted** — see its section below.

- **B1 (DONE, local).** Root cause re-diagnosed: the dominant bug is not
  "orphan diacritics on their own line" but **TeX accent-before-base** — these
  PDFs place the accent glyph *before* its letter, separated by a space, so
  fitz extracts `sv ̄ah ̄a` for `svāhā`, `Ch ́enier` for `Chénier`. Measured
  **11,636 cases across 46 books** (15SecretOfTheVeda 2,487; 19EssaysOnTheGita
  1,562; 16Hymns 1,516…); every one also broke FTS5 search for that word. Fixed
  in `split_pdf.py` `_reorder_stranded_marks()` (regex move mark→after base +
  NFC), applied to body + footnote lines. Corpus stranded-mark count **11,636 →
  420**. The residual 420 are out of scope: precomposed orphans on their own
  line (the original Supramental `ṁ`/`ṣ` examples — need x-coordinate data),
  the TeX dot-below `r.t`→`ṛt` pattern, and Hymns legacy-font Devanagari
  mojibake (OCR territory).
- **B (DONE, local).** Boundary fix applied corpus-wide. Per-book section-file
  clear added (guarded by `if sections:` — see watch-out below) so re-runs no
  longer accumulate orphans. Conservation check across all 93 books: **0 over
  threshold, no missing books**; all deltas are small boundary-relocation
  dedup, verified against source PDFs on canaries. Recovered ~88 real sections
  (e.g. 02CollectedPoems: Goethe, God, The Fear of Death).
- **Encrypted-PDF gap found + fixed.** 30/31 LettersOnYoga and 14Vedic are
  **AES-encrypted**; `faiss_env` lacked PyCryptodome, so PyPDF2 silently
  returned no outline and these books were skipped (their live sections were
  stale legacy artifacts that only survived because the old code never
  cleared). `pip install pycryptodome` in `faiss_env` fixed it; they now
  regenerate cleanly (counts match baseline exactly). The guarded clear is the
  safety net if any future book is ever un-processable.
- **New tooling:** `scripts/check_conservation.py` (per-book char-multiset
  conservation, tag/whitespace/mark-insensitive). Baseline snapshot kept at
  `~/Projects/collectedworks/out_chapters_baseline_20260612/`.
- **DEPLOYED 2026-06-26** (tag `deployed-2026-06-26`). Data-only deploy
  (chapters.db atomic swap + out_chapters rsync per DEPLOY.md §0.5/§3; no
  backend/frontend code change). Prod smoke-verified: `svāhā` search returns
  hits, Hymns chapter renders clean (0 stranded marks), CollectedPoems "Light"
  footer gone. EC2 snapshot at `backups/collectedworks21-pre-release-2026-06-26.tar.gz`;
  local pre-rebuild db at `backend/db/chapters.db.prerebuild-20260625`.
- **Also shipped:** CollectedPoems running page-footer strip (period/place
  titles like "England and Baroda, 1883–1898" that leaked mid-poem) via
  `extra_header_phrases` in book_mapping.json — 279 → 7 footer lines, 0
  mid-poem. Surfaced during local testing, not part of the original B/B1/C.

---

## C — Corpus-wide italic quote fragmentation

**Symptom.** Inline Sri Aurobindo quotes (italic) fragment across lines with
blank-line gaps, e.g. on a chapter page a quote renders as several separate
italic paragraphs instead of one continuous run.

### Tier-1 execution result (2026-07-11) — 2 shipped, 5 held

Worked the Tier-1 list per-book with a rendered-paragraph-diff gate. **Key
finding: the tier metric (italic↔italic adjacencies) over-predicts safety.**
Setting `enable_italic_breaks:false` removes the blank at *every* italic↔prose
boundary, not just the measured italic↔italic ones — so in books with Q&A,
dramatic dialogue, or set-off letters it merges distinct items. The metric
only reliably predicts safety for **pure verse/quote-commentary expository
books**.

- **SHIPPED (validated clean, 0 real set-off merges):**
  `15TheSecretOfTheVeda` (−264 paras) and `19EssaysOnTheGita` (−14). Both
  quote Sanskrit verse inline with commentary; every merge is a fragmented
  verse rejoining its sentence. Flag left `false` in book_mapping.json.
- **HELD — reverted to default (flag removed):**
  - `MCW-Vol7-QA-1955` — Q&A book; flag merged 486 italic **questions** into
    their prose answers (38% of merges). Hard regression.
  - `18KenaAndOtherUpanishads` — dramatic dialogue; speaker labels
    ("Nachiketas speaks:") merged into the following verse; also heavy
    Devanagari mojibake.
  - `29LettersOnYoga-II`, `32TheMotherWithLettersOnTheMother`,
    `Light to Superlight` — letters/compilation class (the one the earlier
    global attempts regressed). Flagged merges were mostly good quote-rejoins,
    but held out of caution.
- **Reclassification:** the 5 held books move to the **Tier-2 treatment**
  (per-book continuation heuristic — join only when the next line continues
  the sentence: starts lowercase / no sentence-end punctuation before the
  break — NOT a blanket flag flip). The flag flip is now understood to be
  safe *only* for verse/quote-commentary books; apply it to future Tier-1
  candidates only after confirming the book has no Q&A / dialogue / letter
  structure, and always gate on the rendered-paragraph diff.
- **Validation harness kept** at scratchpad `tier1_validate.py` (set-off-merge
  detector: a fully-italic paragraph ending in terminal punctuation that
  merges = likely a wrongly-absorbed set-off item).

### Prioritized attack plan (measured 2026-07-11) — start with Tier 1

Per-book ranking of the `</i>\n\n<i>` adjacencies, scored by the **strict**
signal: the next italic run starts **lowercase**, i.e. an unambiguous
mid-sentence break. (This deliberately drops false positives that the raw
frag count produces — e.g. Savitri's `Canto One` / `The Symbol Dawn` heading
pair, whose next line is capitalised, so it does *not* count.) `ratio` =
strict-wrong / total adjacencies, and is the **risk gauge**: near-100% means
almost every break in the book is wrong, so the cheap per-book flag flip is
low-risk; a low ratio means most breaks are legitimate set-off items
(dialogue turns) that the flag would wrongly merge — see the two reverted
attempts below.

Reproduce: strict scorer over `out_chapters/**/section_*.txt` (script kept at
scratchpad `rank_c_candidates.py`; the strict variant counts only
lowercase-next).

**Tier 1 — ratio ≥ 85%, do first via per-book `enable_italic_breaks: false`.**
Spot-checked 2026-07-11: every one is genuine fragmentation (hyphenated-word
splits like `madhu-` / `mān ūrmiḥ`, `scru-` / `tinise`, and mid-sentence
verse/quote breaks), so the flag flip is the right fix and the over-merge
risk is minimal.

| book | wrong/total | ratio |
|------|-------------|-------|
| `sriaurobindo/15TheSecretOfTheVeda` | 42/42 | 100% |
| `sriaurobindo/32TheMotherWithLettersOnTheMother` | 37/43 | 86% |
| `mother/MCW-Vol7-Questions-And-Answers-1955` | 23/27 | 85% |
| `sriaurobindo/29LettersOnYoga-II` | 13/14 | 93% |
| `disciples/Light to Superlight` | 9/9 | 100% |
| `sriaurobindo/19EssaysOnTheGita` | 7/7 | 100% |
| `sriaurobindo/18KenaAndOtherUpanishads` | 5/5 | 100% |

**Tier 2 — high count but mixed ratio (37–73%). Do NOT flag-flip these** —
they carry many legitimate dialogue-turn breaks, so the flag would over-merge
(exactly the reverted-attempt failure). These need the per-book continuation
heuristic instead (join only when the next line continues the sentence).

| book | wrong/total | ratio |
|------|-------------|-------|
| `mother/New-Correspondences-of-the-Mother-2` | 105/194 | 54% |
| `sriaurobindo/10-11RecordOfYoga` | 69/94 | 73% |
| `mother/MCW-Vol12-On-Education` | 67/100 | 67% |
| `mother/New-Correspondences-of-the-Mother-1` | 51/106 | 48% |
| `mother/MCW-Vol17-More-Answers` | 49/132 | 37% |
| `mother/The Mother - Agenda Vol1…13` | 16–35 each | 16–53% |
| `mother/MCW-Vol6/Vol13/Vol15`, `sriaurobindo/28LettersOnYoga-I` | 14–27 | 41–73% |

**Validation gate (applies to every book, both tiers) — unchanged from the
reverted attempts:** regenerate the candidate with the change, then diff
baseline-vs-new *rendered paragraphs* (reuse `routes.py`
`_reflow_lines_for_prose`), NOT raw frag counts. Confirm set-off block quotes
/ dialogue turns did not wrongly merge before shipping. Then it rides the
normal rebuild + DEPLOY.md §3 data path.

**Two root causes — one is already fixed corpus-wide, one is not:**

1. **Splitter `enable_italic_breaks` (NOT fixed corpus-wide).**
   `split_pdf.py` (the `enable_italic_breaks` block, ~L965–975) inserts a blank
   line at *every* italic↔prose transition. The backend splits paragraphs on
   blank lines ([routes.py](../backend/app/routes.py) `raw_blocks = re.split(r'\n\s*\n+', raw)`),
   so each fully-italic line becomes its own paragraph → fragmentation.
   - **Fixed for one book only** via `book_mapping.json` →
     `Satprem-...-Adventure...pdf` → `"enable_italic_breaks": false`.
   - **Remaining decision:** flip the default to `false` globally, or set the
     flag per affected book. **Risk:** some books may use italic for genuinely
     *set-off block quotes* that should stay separate paragraphs — disabling
     could merge them into surrounding prose. Validate on heavily-italic books
     before flipping globally.
   - **Scale:** ~1695 `.txt` files corpus-wide carried the `</i>\n\n<i>`
     split-quote pattern (measured 2026-06-09).

2. **Reader reflow `_end_punct_rx` (ALREADY FIXED, live 2026-06-09).**
   Reflow treated a bare closing quote/bracket as a sentence end, forcing a
   paragraph break (e.g. after `…of "clearing"`). Changed in
   [routes.py](../backend/app/routes.py) `_end_punct_rx` from
   `[.!?…"”)\]]\s*$` → `[.!?…]["”)\]]*\s*$` (require real sentence punctuation
   before any closing quote/bracket). **This is global and already deployed.**

**Validation approach for #1:** regenerate candidate books with the flag off,
render spot-check the heavily-italic ones (Satprem *The Mind of Cells*, CWSA
*Letters on Yoga* volumes, etc.), confirm set-off block quotes do not wrongly
merge into adjacent prose. Compare against current live render.

**TWO APPROACHES TRIED AND REVERTED (2026-06-25). Don't repeat these:**

1. **Default-flip `enable_italic_breaks` → False.** Render-diff on canaries
   showed it merged genuine set-off items: Agenda *dialogue turns* and Satprem
   set-off Sri Aurobindo block quotes collapsed into surrounding prose (24/29
   Mind-of-Cells sections regressed). Rejected.
2. **Fix the italic-line *detector*** (count a line as italic when stripping
   its `<i>…</i>` runs leaves no word chars, instead of the strict
   `^\s*<i>.*</i>\s*$`). Helped poem/quote books (02CollectedPoems 145→8 frags)
   but **regressed letter-heavy books**: New-Correspondences, nirodbaran,
   mona-sarkar, Agenda Vol11 each *gained* frags. Root cause: **inline
   italic-within-italic** — a journal title set in roman *inside* an italic
   letter (`<i>…for </i>Mother India<i>. …`) makes continuation lines flip
   italic↔prose, so the detector inserts a blank mid-sentence. Confirmed via
   render-diff: `…hope of receiving` / [blank] / `from you "Words" for …` split
   one sentence into two paragraphs. Rejected.

**Conclusion:** C is genuinely a *per-book* problem; no blanket flag/detector
change is safe corpus-wide. Frag count is also a poor proxy (a `</i>\n\n<i>`
adjacency is correct for distinct dialogue turns, wrong only for one continuous
quote). A real fix must distinguish "continuous quote across a line break" from
"distinct set-off items" — likely per-book opt-in plus a continuation heuristic
(next line starts lowercase / no sentence-end punctuation before the break).
Validate each candidate book with a baseline-vs-new *rendered-paragraph* diff
(reuse the reflow logic from `routes.py` `_reflow_lines_for_prose`), not a raw
frag count.

---

## B — Corpus-wide chapter-boundary fix (full rebuild)

**Status.** Splitter boundary fix is committed (`collectedworks` `4fd21b1`) but
**only one book was regenerated + deployed** (Satprem – Adventure of
Consciousness, 2026-06-09). A full rebuild would apply it to all ~96 books —
**untested**.

**What the fix does.** Splits the boundary page at the next chapter's heading
so a chapter's text that flows past a page break is no longer leaked into the
next section (and short chapters whose intro was entirely leaked are recovered).
See `split_pdf.py` `_find_title_start` + the `is_boundary` block.

**Scale.** ~242 sections across ~12 books showed the mid-page-heading leak
(measured 2026-06-09): `02CollectedPoems` (123 — **scrutinize, likely false
positives**), Satprem Adventure (done), `Light to Superlight` (27), Govindbhai
(24), Satprem *Mind of Cells* (16), Purani *Evening Talks* (4), a few others.

**Before any corpus deploy — run the automated safety net:**
- **Text-conservation check** per book: compare the word-multiset of all
  section files baseline-vs-new. The fix must *relocate* text, never lose or
  duplicate it. (Satprem book: Δ −54 chars over 650 K; only heading strings
  differed.) Build a clean baseline (fix stashed) and a clean new tree, diff.

**Watch-outs discovered while doing the one-book deploy:**
- `split_pdf.py` does **not** clear a book's output dir before writing. Because
  the fix renumbers/inserts sections, re-runs **accumulate orphan section
  files** (saw 145 files in a book that should have ~79). A clean rebuild must
  `rm section_*.txt raw_section_*.txt` per book first — or add a per-book clear
  to `split_pdf.py`. `build_chapter_index.py` indexes *every* `section_*.txt`,
  so orphans would corrupt the DB.
- **Special books not produced by `split_pdf.py` alone** — don't clobber:
  - On-Aphorisms: `split_aphorisms.py` + `split_aphorism_sections.py`
  - Sanskrit OCR (Hymns to the Mystic Fire): `ocr_sanskrit_pdf_split.py`
    (writes `ocr_out_chapters`, not `out_chapters`)
- The fix can **recover previously-missing sections** (Satprem gained 8 real
  chapters). The title-only guard suppresses part-divider stubs; verify
  recoveries are real content, not stubs.

---

## D — Splitter de-hyphenation damage (D1 done; D1-residual + D2 open)

**How this surfaced.** A reader comparing
`/read/disciples/nirodbaran-talks-with-sri-aurobindo-ii/11-april-1940`
against the PDF found eight differences. Six were render-time and were fixed
and deployed on 2026-09-19 (`9b8e97c`). The two below are baked into
`out_chapters/` and `chapters.db`, so no serve-time change can reach them.

**Shared root cause.** `merge_lines()` in `~/Projects/collectedworks/scripts/split_pdf.py`
(line 340; the hyphen branch at 348) de-hyphenates a line-wrapped word by
pulling only the *alphabetic* fragment up to the previous line and leaving the
remainder where it sat:

```
PDF   'X made a mis-' / 'take, for which he got...'
txt   'X made a mistake' / ', for which he got...'
```

Note `_repair_page_joins()` (line 486) already does this correctly for hyphens
that fall across a *page* break (`stripped_prev + nxt_raw.lstrip()` — the whole
continuation line is consumed). `merge_lines()` is the inconsistent one.

### D1 — Real compound hyphens are eaten  [FIXED]

`merge_lines()` strips **every** trailing `-`, including hyphens that belong to
the word. `non-` + `Communists` becomes `nonCommunists`; likewise `proGerman`,
`antiBritish`, `proAllies`, `nonBengalis`, `preVedic`.

**Why it matters beyond looks:** the glued occurrences are unfindable. FTS5
indexes `nonCommunists` as one token, so no query reaches it. Note the damage
is narrower than "search is broken": the porter tokenizer splits a query like
`Anglo-Indian` into two tokens and still matches the *correctly* spelled
instances elsewhere, so that query looks fine. It returns nothing only for a
compound whose sole instance in the corpus is the glued one -- 59 of them.

**Scale:** ~60–80 real English cases. A naive `[a-z]{2,}[A-Z][a-z]{2,}` scan
reports 1,174, but the bulk is Sanskrit transliteration noise from B1 (716 in
16Hymns alone) — filter by known prefixes (`non|self|pre|post|anti|pro|semi|
sub|inter|multi|well|half|quasi|ex|counter|over|under|co|re`) to get the real
list.

**Fix:** keep the hyphen when the following fragment is capitalised, i.e.
narrow the `re.match(r'\s*([A-Za-z]+)', next_line)` fragment class to
lowercase for the de-hyphenation branch. Cheap in the splitter; needs a
rebuild, or a targeted repair pass over the ~80 known words in both
`out_chapters/` and `chapters.db` (FTS rows too).

### D1 — DONE, deployed 2026-09-19

Fixed in the splitter (`collectedworks` `3e7bc91`): `merge_lines()` keeps the
hyphen when the continuation fragment is Capitalised-then-lowercase, and still
drops it for an all-caps wrap (`PONDI-`+`CHERRY`). Already-built data repaired
in place by `backend/scripts/helpers/restore_compound_hyphens.py` -- 460
replacements in 322 `.txt` files, 406 in 307 chapters.db rows, 334 words across
82 books. The script re-derives everything from the source PDFs, so it is safe
to re-run after any rebuild; add it to the §3 post-rebuild fixups.

Verified on prod: all 12 sampled compounds now return hits on `/api/text_search`
(`mode=exact`); controls `PONDICHERRY` / `COM-PLETE` stayed glued; conservation
exact at +406 chars with row and book counts unchanged.

**Careful with which endpoint you measure.** `/api/search` is the *semantic*
FAISS path and reads `backend/indexes/`, not chapters.db -- its `exact` param is
ignored entirely. The FTS path is `/api/text_search` with `mode=all|all_words|exact`.
Measuring D1 on `/api/search` gives meaningless numbers. (The FAISS index dates
from Apr 2025, predates this bug and already holds the correct hyphens, so it
never needed repairing -- but it is stale in other respects.)

### D1-residual — the same loss with a LOWERCASE continuation

`consciousness-` + `force` -> `consciousnessforce`; `self-` + `imposed` ->
`selfimposed`. 4 known occurrences (Life Divine ×2, Hour of God, Satprem
*Adventure*). Shape cannot separate these from a genuine soft hyphen
(`un-`+`happy`), which is why D1 deliberately scoped itself to capitalised
continuations.

**A dictionary split does NOT work** -- tried and rejected 2026-09-19.
`/usr/share/dict/words` (web2) flags 2,475 tokens / 19,482 occurrences,
including `bringing` -> `brin-ging` and `creating` -> `crea-ting`, because web2
carries enough archaic fragments to split almost anything.

**What should work instead:** ask the corpus, not a dictionary. For each
PDF line-end hyphen with a lowercase continuation, test whether the hyphenated
form occurs *mid-line elsewhere in the corpus*. `consciousness-force` does;
`unhappy` never appears as `un-happy` mid-line. That is a data-driven
discriminator with no external wordlist. Unmeasured so far -- size it before
committing to it.

### D2 — Paragraph breaks invented at line wraps

`_end_punct_rx` in `backend/app/routes.py` splits a paragraph whenever a line
ends with sentence punctuation. That is load-bearing — in the talks volumes it
is the only thing separating consecutive speaker turns, which carry no blank
line between them. But it also fires when a sentence merely *ends at a line
wrap* mid-paragraph, inventing a break the PDF does not have. Two on the page
above (`...hasn't come here yet.` / `...inheritance of the age.`).

**Scale:** of 77,791 breaks the rule creates, **~8,334 (11%)** follow a
full-measure line and are therefore probably spurious. That is a proxy
(character count vs. the block's longest line), not ground truth.

**Why it cannot be fixed at serve time:** the text alone does not say whether a
line ended because the paragraph ended or because it hit the right margin. The
real signal is geometry — a paragraph's last line stops short of the text
block's right edge. That means capturing it in the splitter (fitz gives a bbox
per line) and encoding it in the `.txt`, e.g. by emitting a real blank line at
genuine paragraph ends and letting reflow stop guessing.

**Watch out:** this would be the first change to make the `.txt` paragraph
structure authoritative. Sequence it *after* D1 and fold both into one rebuild
— and re-read the slug-churn warning in `project_slug_churn_seo` before
starting, since any re-split shifts positional `-N` slug suffixes and kills
indexed URLs unless a 301 map is emitted.

---

## Rebuild + deploy reference

**Splitter build (local test, no auto-sync):**
```
# in ~/Projects/collectedworks/scripts (faiss_env)
#   clear per-book section files first to avoid orphans
python split_pdf.py            # all books (or --only "<Book>.pdf")
SKIP_SERVING_SYNC=1 python build_chapter_index.py
```

**Post-rebuild fixups (DEPLOY.md §3 — pipeline keeps reintroducing these):**
```
sqlite3 backend/db/chapters.db < backend/scripts/helpers/strip_oversized_sections.sql
python3 backend/scripts/helpers/recover_letters_verse_breaks.py --db
python3 backend/scripts/helpers/normalize_ligatures.py --txt
python3 backend/scripts/helpers/restore_compound_hyphens.py --write   # D1, see above
python3 backend/scripts/helpers/normalize_sanskrit_runs.py      # see B1 in memory
```

DEPLOY.md §3 is the authoritative copy of this list — it carries the flags,
the ordering rationale and the dry-run-first advice. Two things this short
version gets wrong and §3 gets right: `strip_oversized_sections` is now a `.py`
(the `.sql` listed above was superseded 2026-08-02 because it named rows by
hand and had missed two), and `build_slug_redirects.py` belongs in the sequence
too. Trust §3 over this block.

**Deploy (see [docs/DEPLOY.md](DEPLOY.md)):** §0.5 backup → §1 code rsync →
§3 data (chapters.db atomic swap + out_chapters) → restart `collectedworks` →
§4 smoke. Deploys are rsync-based (not `git pull` on EC2). Note: DEPLOY.md §6
calls the GitHub remote "frozen", but the `project_remote_push_blocked` memory
(2026-06-07) says push to `main` succeeds after the filter-repo cleanup —
verify before relying on either.

---

## Related (in memory)

- **B1 — Sanskrit orphan diacritics** in the splitter's fitz extraction
  (Hymns 925, Vedic 533 cases). Needs `page.get_text("dict")` rewrite. See the
  `project-outstanding-tasks` memory for full detail.
