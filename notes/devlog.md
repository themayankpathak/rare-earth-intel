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
