# Build log

Short dated entries, written at the end of each session.

## 2026-09-21 — Day 1

**Did:** Built the 20-row ground truth for the MP Materials FY2025 10-K. All workbook checks pass,
including the reconciliation: concentrate revenue / REO sales volume = $4,706.57 vs stated $4,707 (0.009%).

**Went wrong:** The first 10-K copy was a browser print-to-PDF with no text layer (221 image pages).
Replaced it with the original Workiva PDF (121 pages, SHA-256 recorded in the sources sheet).
Every pdf_page reference changed; printed page numbers did not.

**Went wrong:** `.gitignore` had `data/`, which ignores the whole folder, so the ground truth could not
be committed and git gave no warning. Changed to `data/*` + `!data/ground-truth/`.

**Found:** Check 3 compared the text "TRUE" (from the dropdown) against a boolean, so it would have
flagged every correct comparative row. Rewrote it with SUMPRODUCT.

**Decision:** The ground truth was drafted with AI assistance. I verify each row against its cited page on Day 2.

**Next:** Verify the 20 rows; first script that opens the PDF and prints a page.

## 2026-09-21 — Day 2 (same day as Day 1)

**Did:** First script (`scripts/page_looker.py`): prints any page of the 10-K by its printed page number.
Confirmed the code sees the same numbers as the ground truth on printed pp.44 and 49.

**Found:** Table lines carry $ change and % change columns after the three years; negatives are in
parentheses; em-dashes mean no value; footnote markers like "(1)" stick to labels. Printed p.49 has two
scale headers ("in whole units", then "in thousands"), and section headings carry meaning, so the parser
must read top to bottom and remember the last scale header and heading it passed.

**Decision:** Skipped manual row-by-row review of the ground truth. Values are machine-checked instead.

## 2026-09-22 — Days 3–7

**Did:** Line parser, page extractor, label map, 28-column row builder, scorer, self-checks, chart.
README rewritten to match what is built.

**Result:** 18 of 20 ground-truth rows found (GT18/19 are on p.29, not parsed). All 13 fields correct on
all 18. 64 of 64 self-checks pass. Revenue / volume matches MP's stated price within 0.01% for all three years.

**Found:** The scorer caught a format bug in the ground-truth CSV: exporting from Excel turned text "TRUE"
into "True", so is_comparative scored 0/18. Fixed the data, not the comparison.
Same label, different number: "NdPr oxide and metal" is $115.1m on p.44 but $9.3m (related-party) on p.105.
PPA income sits under a "Revenue:" heading but is not revenue.
The pairing trap (total revenue / concentrate volume) is 0.4% off in FY2023 and 435% off in FY2025.

**Decision:** Ship first; learn the Python properly before interviews. Code written with AI assistance.

**Next:** Buffer days. Stretch: p.29 parsing, parse_quantity for Chinese units.

## 2026-10-01 — Day 11

**Did:** Parsed printed p.29 (Estimated distribution of TREO content). Text cleaner keeps a
trailing "%" in raw_text, as printed. Extractor takes per-page year columns and starting scale;
p.29 has neither, so it is read with period `not_applicable` and scale 1. Build step leaves
fiscal-year fields blank when the period is not a fiscal year. Label map: four p.29 lines
(Ce, La, NdPr, SEG+). New self-check: element shares sum to 100%.

**Result:** 20 of 20 ground-truth rows found, 13/13 fields correct on all 20. 73 of 73 checks pass.
EX01–EX30 unchanged; p.29 adds EX31–EX34.

**Found:** Adding p.29 with no scale header gave its rows an empty scale_factor, and one empty
value turned the whole column from 1000 into 1000.0. Scoring reads everything as text, so
scale_factor dropped to 0/18 on rows that were never touched. Fixed by giving p.29 a real scale.
Also: the new composition check failed (0 elements, sum 0%) when the label map had not been
saved — it caught a missing-data problem on its first run.

**Decision:** p.29 is read last so existing row_ids stay stable (schema: never renumber).
All four elements mapped, not only the two in the ground truth, so the sum check works.
`La` and `SEG+` added as material values.

**Next:** Update CLAUDE.md handoff. Optional: FY2024 10-K run (self-checks only).
