# Backlog — collectedworks21 / splitter

Deferred work items with enough context to pick up cold in a new session.
Splitter repo lives at `~/Projects/collectedworks` (sibling). Serving repo is
this one. Conda envs: splitter = `faiss_env`, serving = `collectedworks_env`.

---

## C — Corpus-wide italic quote fragmentation

**Symptom.** Inline Sri Aurobindo quotes (italic) fragment across lines with
blank-line gaps, e.g. on a chapter page a quote renders as several separate
italic paragraphs instead of one continuous run.

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
python3 backend/scripts/helpers/normalize_sanskrit_runs.py      # see B1 in memory
```

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
