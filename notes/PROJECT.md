# Rare Earth Intel

A price and supply intelligence system for the NdFeB magnet value chain, built
from company annual reports and public agency data in English and Chinese.

The system extracts numeric facts from source documents into a single structured
table, reconciles them across sources, and produces charts that show how
reported prices compare against what the underlying materials imply they should
be.

**Status:** Day 1 of a 10-day sprint (ship date 30 Sep 2026). Original Workiva
PDF of the MP Materials FY2025 10-K obtained (real text layer, 121 pages). 20
ground truth rows built (AI-assisted draft, being verified by the author against
the cited pages); all workbook checks PASS; `raw_text` found on the cited page
for all 20 rows. No extraction code written yet.

> **Note for anyone (including an AI assistant) reading this cold:** this file is
> the complete project context. It is written to be self-contained. Sections
> marked **[LEARNED]** record things discovered by reading real documents, not
> assumptions. Do not treat the traps list as theoretical; every entry has
> already caused or nearly caused an error.

---

## Why this project

I work in project management at N.A.N. MagneTech, a company building India's
first mine-to-magnet NdFeB facility at Naidupeta. Part of my work there involved
reconstructing NdFeB price series by grade across several years from Chinese
sources and company annual reports, and cross-checking them to test whether
reported figures held up.

That work was done by hand, and it belongs to the company. This project turns
the *method* into something repeatable and auditable, using only public
documents.

My background: B.Tech from NIT Calicut, currently in a non-technical role,
moving toward data engineering and ML. I know the rare earth domain well enough
to tell when a number is wrong. I am learning the engineering as I build this.

**Target roles this is built for:** data science / data engineering roles that
value reproducible pipelines, data quality, and evaluation (e.g. Nielsen Data
Science), and data-operations roles that value sourcing hard-to-get data and
owning quality end to end (e.g. Cartesia Data & Strategy). It is deliberately
*not* a computer vision or model-training portfolio project.

---

## Scope: core vs future work

The original plan ran 20 weeks and included a bilingual pipeline, cross-source
reconciliation, and a chat interface. That is too large to carry alongside a
demanding day job, and an unfinished large project is worth less than a finished
small one.

**CORE (this is the deliverable, 4–6 weeks):**

1. One company, one product line, extracted by hand into the v2 schema
2. Twenty hand-verified ground truth rows
3. A script that extracts the same rows automatically
4. Field-level accuracy measured against the ground truth
5. One chart
6. A README stating what was checked, what was found, and what is known to be
   wrong

**FUTURE WORK (belongs in the README as a roadmap, not in the build):**

- Chinese-language sources and the bilingual path
- Cross-source reconciliation (customs data, USGS)
- Physical floor / bill-of-materials analysis
- Dy substitution trend
- Question-answering interface

The chat interface is last and may never be built. Building it first means three
weeks polishing a UI over an empty table.

---

## Architecture: two lanes

The single most important design decision. **The LLM does not do arithmetic over
retrieved text.** It will confidently return wrong numbers and they will be hard
to catch.

```
Ingest and OCR (mixed EN / ZH documents)
        |
Parse once, keep provenance (doc, page, language, tables)
        |
        +---------------------------+
        |                           |
   TEXT LANE                   NUMERIC LANE
   chunks, embeddings,         schema extraction
   citations                   into a table
   (qualitative questions)             |
        |                     Reconcile and flag
        |                     (cross-source, implied vs reported)
        |                           |
        +------------+--------------+
                     |
              Answer layer
       routes numeric vs qualitative,
       cites source, refuses when thin
```

Qualitative questions go to the text lane. Anything numeric is answered from the
structured table, never from retrieved prose.

---

## Source acquisition rules **[LEARNED]**

**Check for a text layer before doing anything else.** The first MP Materials
10-K downloaded for this project was a browser "Print to PDF" of the EDGAR HTML
page: 221 rasterised images, 95 MB, zero extractable text. `pdftotext` returned
20 characters across 20 pages, all of them form feeds. Reading it required OCR of
all 221 pages, which introduced errors (`NdPr` came out as `NaPr` and `NéPr`).

Diagnostic, run on every document at download time:

```bash
pdfinfo  document.pdf     # page count, producer
pdffonts document.pdf     # EMPTY font table => no text layer => it is a scan
pdftotext -f 1 -l 5 document.pdf - | wc -c   # near zero confirms it
```

Record the result in the `sources` sheet under `has_text_layer`.

**Prefer the original format over a PDF.** SEC filings are published as HTML with
real `<table>` elements that pandas reads directly, plus XBRL. Downloading the
`.htm` removes both the OCR step and the PDF table-parsing step. A PDF is a
fallback, not a default.

**Producer string is a tell.** `Microsoft: Print To PDF`, `Chrome`, or a scanner
name in `pdfinfo` output means treat with suspicion.

---

## Schema v2

Every extracted number is a row. **One number from the page becomes one row.** A
revenue figure and a volume figure from the same table line are two separate
rows, linked by sharing the same entity, segment, material, chain_stage and
period. Division happens later, in code, never in the spreadsheet.

A number is never extracted alone. It is always accompanied by the context that
identifies what it measures.

### Fact identity

| Field | Notes |
|---|---|
| `row_id` | Stable. Referenced by `derived_from`, so never renumber |
| `entity` | Who the number is about: MP Materials, Lynas, JLMAG, USGS, China |
| `entity_scope` | consolidated / segment / subsidiary / site / country / global |
| `segment` | Required when `entity_scope` = segment. MP: Materials or Magnetics |
| `material` | NdPr, Dy, Tb, total_REO, NdFeB, mixed_REC. Never blank |
| `chain_stage` | ore, concentrate, oxide, metal, alloy, sintered_magnet |
| `metric` | production_volume, sales_volume, revenue, avg_selling_price, purchase_price, composition_pct, reserve_tonnage |
| `basis` | contained_REO / oxide_equivalent / gross_weight / dry_weight |
| `period` | The fiscal period the number describes, not the filing year |
| `period_granularity` | FY / H1 / H2 / Q1–Q4 / CY / multi_year |
| `period_end_date` | ISO text. Lynas ends 30 June, MP ends 31 December |

### The value

| Field | Notes |
|---|---|
| `value_reported` | The number exactly as printed, without the scale. 41,992 → `41992` |
| `scale_factor` | Multiplier to base units: 1000 for "in thousands", 10000 for 万 |
| `value_base` | Formula: `value_reported × scale_factor` |
| `unit` | Base unit only: tonnes, kg, USD, USD_per_tonne, g_per_kg, percent |
| `currency` | USD, AUD, RMB, INR, CAD, none. Kept separate from `unit` |
| `price_basis` | basket / single_material / contract / floor_supported |

Splitting `value` into `value_reported` and `scale_factor` is deliberate. A
missed "in thousands" or a mistranslated 万 becomes a single wrong field that
the evaluation can score, instead of a value that is silently wrong by four
orders of magnitude and indistinguishable from a correct extraction of some
other number.

### Provenance and quality

| Field | Notes |
|---|---|
| `derivation` | as_reported / derived. Did the issuer print this, or did I compute it? |
| `derived_from` | Semicolon-separated row_ids. Required when derived. The audit chain |
| `is_comparative` | TRUE when the figure is a prior-year comparative inside a later document. Makes restatements findable by filter |
| `doc_type` | annual / financial / quarterly / agency / technical_report |
| `source_document` | Filename. URL and text-layer status live on the `sources` sheet |
| `pdf_page` | Page number in the PDF file |
| `printed_page` | Page number printed on the page. **In the original MP 10-K PDF, pdf = printed + 4.** (The earlier browser-printed copy had an irregular offset.) Anyone opening the real document looks for the printed one |
| `raw_text` | The exact source string as printed, e.g. `$ 41,992` or `1.2万吨` |
| `language` | en / zh |
| `confidence` | high / low. Low routes to the review queue |
| `notes` | Anything that would make a future reader misuse the row |

`raw_text` is not optional. Without it, no extraction can be audited and no
magnitude error can be debugged. It also enables a free check: assert that the
string actually occurs in the parsed page text. That catches hallucinated
numbers with no ground truth required, on every row, from day one.

### Controlled vocabularies

All categorical fields draw from a `lists` sheet (later a CSV in the repo). To
add a term, add it to the list, never free-type it into a row.

---

## Extraction procedure: two passes **[LEARNED]**

Filling 28 fields while simultaneously hunting through a PDF is what makes
ground-truth building feel impossible. Split it.

**Pass one — capture (14 fields).** What is expensive to redo because it means
going back into the document.

`row_id`, `entity`, `material`, `metric`, `period`, `period_end_date`,
`value_reported`, `scale_factor`, `unit`, `currency`, `source_document`,
`pdf_page`, `raw_text`, `language`

Mechanical procedure, about a minute per row:

1. Pick one number in one table.
2. Copy it into `raw_text` exactly as printed, before thinking about anything
   else.
3. Read off the surroundings: the row label gives material and chain stage, the
   column header gives the period, the table header gives scale and currency
   ("in thousands", "$"), the section heading gives the metric.
4. Next number.

**Pass two — classify (the rest).** Done over rows that already exist, without
reopening the PDF. This is where judgement lives: `entity_scope`, `segment`,
`basis`, `chain_stage` refinement, `price_basis`, `derivation`,
`is_comparative`, `confidence`, `notes`.

Pass two is much faster than it looks, because by then the number and its page
reference are already captured and the only task is classification.

---

## Verification

Three checks. The third requires domain knowledge and is the reason this project
is worth building.

**1. Internal consistency.** A report states revenue, volume, and often average
selling price. Divide revenue by volume and check it matches the stated price.

Confirmed on MP Materials FY2025 10-K, all three years, to under 0.01%:

| Year | Revenue | Sales volume | Implied | Stated |
|---|---|---|---|---|
| 2025 | $41,992k | 8,922 MT | $4,706.6 | $4,707 |
| 2024 | $144,363k | 32,703 MT | $4,414.4 | $4,414 |
| 2023 | $252,468k | 36,837 MT | $6,853.7 | $6,854 |

Also confirmed on Lynas FY2022: A$920.0m ÷ 15,263 REOt = A$60.3/kg, matching the
stated figure. **Both of these are basket prices** (see traps).

**2. Cross-source.** Company-reported export volumes against the importing
country's customs data. Company-reported production against USGS global
estimates. Two independent parties describing the same physical flow should
agree. **This check is meaningless without the `basis` field** — see the
contained-REO trap below.

**3. Physical floor.** A magnet cannot sell below its material cost. Given the
bill of materials for a grade and input prices for NdPr, Dy and Tb, compute the
implied floor. A reported price beneath it is either wrong or subsidised.

Two parameters must be explicit, not buried in the calculation:
- **Yield.** Sintered magnet production loses a substantial fraction of alloy
  mass to machining swarf, so material cost per kg of *finished* magnet is
  higher than the bill of materials implies. A floor computed without a yield
  factor sits too low to catch anything.
- **Inventory lag.** A magnet sold in Q3 was made from alloy bought months
  earlier. A price under today's floor may just be lag.

Plus range checks per material to catch magnitude errors automatically. **Make
these era-aware or deliberately wide.** A band of RMB 1,500–5,000/kg for Dy
oxide is fair for recent years, but the 2011 spike took it roughly an order of
magnitude above that. Wide bands still catch what matters: a 万吨 error is
10,000×.

Target: high-90s field accuracy with everything else surfaced for review. Not
100%. Silent errors are worse than flagged ones.

---

## Known traps

Each has already caused or nearly caused an error.

### Volume and price

- **Production ≠ sales ≠ internal transfer.** Companies produce and sell
  different amounts. The difference is usually inventory, but not always. **MP
  FY2025: produced 50,692 MT of concentrate, sold 8,922 MT — 17.6%.** That is
  not a stockpile decision; sales to China ceased in July 2025 and most output
  was fed internally into separation and sold as NdPr instead. Implied price
  needs volume *sold*, and the gap needs a third category for internal transfer.
- **"MT" may not mean tonnes of product. [LEARNED]** MP's unit of production and
  sale is a tonne of *contained REO*, while the concentrate itself is above 60%
  REO by weight. So 8,922 MT of REO is roughly 14,900 tonnes of physical
  material. Customs authorities weigh what crosses the border. Comparing the two
  without regrading produces a ~40% discrepancy that looks like fraud and is
  arithmetic. This is what the `basis` field exists for.
- **Volumes may be synthetic. [LEARNED]** MP's NdPr Sales Volume is stated on an
  *oxide-equivalent* basis, converting metal sales at an assumed ratio of 1.20
  (100 MT of metal enters the KPI as 120 MT). The number is partly a modelling
  assumption, not a measurement.
- **NdPr ≠ total REO.** Total REO includes cerium and lanthanum, which are nearly
  worthless. MP's own concentrate is 50.2% Ce, 32.3% La, 15.7% NdPr, 1.8% SEG+
  (10-K printed p.29). Dividing total revenue by total REO tonnes gives a meaninglessly
  low price.
- **Basket prices are not material prices. [LEARNED]** Lynas A$60.3/kg and MP
  $4,707/t are both blended across the full REO mix. Putting either on the same
  chart as an NdPr oxide input price reproduces exactly the trap above. Hence
  `price_basis`.
- **Chain stage matters.** MP sells NdPr oxide; JLMAG sells sintered magnets.
  Their implied prices are not comparable, and the difference is not an error —
  it is the value-add spread, which is the more interesting number.
- **Blended product lines. [LEARNED]** MP's revenue line is "NdPr oxide and
  metal", spanning two chain stages, while the matching volume is
  oxide-equivalent. No honest single `chain_stage` value exists. **Decision for
  this project: keep the row with `chain_stage = oxide`, `basis =
  oxide_equivalent`, `confidence = low`, and the blend explained in `notes`.**
  Apply consistently; Chinese filings do this constantly.

### Scope and reporting

- **Segment ≠ consolidated. [LEARNED]** MP FY2025 total revenue is **$224,441k
  consolidated** but **$160,369k for the Materials segment**. The KPI volume
  table is segment-level. Pairing a segment volume with a consolidated revenue
  overstates price by about 40%. Hence `entity_scope` and `segment`.
- **Intercompany sales sit inside both numerator and denominator. [LEARNED]**
  From Q4 2025 MP's Materials NdPr Sales Volume includes intercompany sales to
  Magnetics, and the $115,131k revenue is gross of the $2,789k elimination.
  Gross ÷ gross is internally consistent, but blends an arm's-length price with
  an internal transfer price. Do not net the elimination out of the numerator
  alone — that gives $56.34/kg from a mismatched numerator and denominator.
- **Revenue without volume is unusable.** MP's $66,861k of magnetic precursor
  product revenue has no disclosed volume. By the selection rule, no row.
- **Issuers withdraw metrics. [LEARNED]** MP **stopped publishing NdPr Realized
  Price per kg** in the FY2025 10-K, stating it is no longer meaningful given the
  Price Protection Agreement. They also expect to stop reporting REO Sales Volume
  and Realized Price per REO MT after 31 December 2025. Any NdPr price in this
  dataset is *derived*, not reported, and must be labelled as such. Series end.
- **Income can sit outside revenue. [LEARNED]** MP booked **$51,016k of Price
  Protection Agreement income** in FY2025, outside revenue. Implied price from
  revenue alone understates what was economically realised. It cannot simply be
  added back: the PPA pays on NdPr products *sold or produced and stockpiled*, a
  different volume base than NdPr Sales Volume.
- **Contractual floors change what the physical floor means. [LEARNED]** The MP
  PPA with the US Department of War sets a **$110/kg NdPr floor** from 1 Oct 2025
  through 2035, with 30% of upside above $110 remitted back once the 10X facility
  hits full capacity. For MP from Q4 2025, a reported price below the material
  floor is neither an error nor a subsidy in the original sense — it is a hedge.
- **Restatements.** A FY2025 report contains FY2023 comparatives. If they
  disagree with the FY2023 report's own figures, something was restated, and why
  is often the most interesting thing in the document. `is_comparative` makes
  these findable by filter.

### Mechanical

- **Currency.** Lynas reports in AUD, MP in USD, Chinese firms in RMB. Convert
  using the FX rate for the period, not today's.
- **Fiscal years differ.** Lynas ends 30 June, MP ends 31 December.
- **万吨 = 10,000 tonnes.** Mistranslating this is an error of four orders of
  magnitude. Handled by `scale_factor`.
- **Scale headers.** "in thousands" above a table is as dangerous as 万 and far
  easier to miss because it looks like formatting.
- **PDF page ≠ printed page. [LEARNED]** In the original MP 10-K PDF, pdf = printed
  + 4 throughout (PDF p.48 is printed p.44). A browser Print-to-PDF copy
  re-paginates and breaks even that. Record both.

---

## Worked source: MP Materials FY2025 10-K **[LEARNED]**

Filing: CIK 1801368, accession 0001801368-26-000008, `mp-20251231.htm`.
Original Workiva PDF: 121 pages (pdf page = printed page + 4). Fiscal year ends 31 December; filed February 2026.

About nine pages of 221 carry extractable numeric facts. That ratio is normal
and will hold for other issuers: volume is not a GAAP disclosure, so it lives
only in the MD&A KPI section.

| PDF p. | Printed p. | Content |
|---|---|---|
| 33 | 29 | Estimated distribution of TREO content: Ce 50.2%, La 32.3%, NdPr 15.7%, SEG+ 1.8% (same figures recur on printed pp.32, 34 inside reserve assumptions) |
| 33–38 | 29–34 | S-K 1300 mineral resources and reserves, tonnage and TREO grade (not re-verified) |
| 47 | 43 | **KPI definitions.** The most important page in the document: defines contained-REO basis, oxide-equivalent conversion, intercompany inclusion |
| 48 | 44 | Consolidated revenue by product, incl. intersegment eliminations ('in thousands') |
| 53 | 49 | Materials segment KPIs ('in whole units') and, below on the same page, segment revenue and PPA income ('in thousands') |
| 54 | 50 | Magnetics segment results |
| 74 | 70 | Customer concentration: A 30%, B 23%, C 31% of FY2025 total revenue |
| 100 | 96 | Note 16 Revenue Recognition: revenue by segment and product, with subtotals; bill-and-hold disclosure |
| 110 | 106 | Note 22 Segment Reporting |

Printed page 29 is worth extracting on its own: those four percentages are the bridge
between any concentrate tonnage and contained NdPr tonnage.

**Read PDF page 47 (printed 43) before extracting anything else from this filing.** Every unit
trap above is defined there.

---

## Chinese-language handling

**Deferred to future work**, but the data model is bilingual from day one so the
switch does not require a migration.

Non-negotiable from the start:

- UTF-8 explicitly on every file open, database column, and CSV write
- A `language` field on every record, even while it is always `en`
- `raw_text` stored alongside every parsed number
- Number parsing as a function `parse_quantity(text, lang)`, not inline regex
- Terminology mapping as a data file, not if-statements
- OCR as a swappable step; the parser takes text and does not care where it came
  from

Rules when Chinese is switched on:

- **Do not translate then extract.** Translation mangles numbers and units and
  destroys citability. Extract from the Chinese directly into the schema, then
  normalise.
- **Do not use generic OCR.** PaddleOCR handles Chinese well and is free. Check
  first whether the document has a text layer.

Terminology mapping (extend as a CSV in the repo):

| Chinese | English |
|---|---|
| 钕铁硼 | NdFeB |
| 镨钕 | PrNd |
| 镝 | Dy |
| 铽 | Tb |
| 烧结 | sintered |
| 元/吨 | RMB per tonne |
| 万吨 | ×10,000 tonnes |

---

## Sources

**Confirmed disclosing volume:**

- **MP Materials** — SEC 10-K, CIK 1801368. FY2020–FY2025 on EDGAR. NdPr oxide
  producer, moving into magnets from 2025. Best disclosure in the industry.
  **Download the `.htm`, not a printed PDF.**
- **Lynas Rare Earths** — ASX (LYC), fiscal year ends June. Sales volume,
  revenue and average selling price stated in a single table with prior-year
  comparatives. *Open question: is sales volume stated separately from
  production volume in the annual report, or is the Q4 quarterly also needed?*
- **JLMAG** — sintered magnet producer, already collected.

**To check:** Neo Performance Materials (SEDAR+, Canada).

**Agency:** USGS Mineral Commodity Summaries, rare earths chapter. Two pages per
year, consistently formatted, 15+ years available. The independent check on
everything companies report.

**India baseline:** IREL (India) Limited annual reports, Ministry of Mines
annual report. Small volumes, but this is the import-dependence position the
whole argument rests on.

**Phase two, Chinese (future work):** China Northern Rare Earth (北方稀土,
600111) first — it is the upstream anchor that sets the oxide price everyone else
pays. Then Zhongke Sanhuan (000970), Ningbo Yunsheng (600366), Yantai Zhenghai
(300224).

**Deliberately excluded:** Proterial, Shin-Etsu, TDK, VAC — magnet business
buried in conglomerate segment reporting with no separate volume disclosure.
Arafura, Peak, Northern Minerals — pre-revenue.

**Selection rule:** if a company does not disclose volume alongside revenue,
skip it. Revenue alone cannot produce an implied price.

Every document is registered on the `sources` sheet with URL, accession, page
count, text-layer status and retrieval date.

---

## Repository layout

```
/data/raw/           source documents, never edited
/data/ground-truth/  hand-verified spreadsheet
/notes/              sources.md, this file
/src/                code
```

Filename convention: `company_doctype_FYyyyy.ext`, lowercase, underscores.
Example: `mp-materials_10k_FY2025.htm`, `lynas_annual_FY2022.pdf`,
`usgs_mcs_rareearths_2026.pdf`.

Fiscal year, not filing year. MP's FY2025 10-K was filed in February 2026.

---

## Timeline

Anchored to a parallel work calendar. **Day-job load peaks from late September
to late November**, which is exactly when the original plan put its critical
milestone. The revised plan front-loads the deliverable so the make-or-break
week falls before the peak.

**Compressed to a 10-day sprint, 21–30 Sep 2026.**

| Day | Date | Deliverable |
|---|---|---|
| 1 | 21 Sep | Ground truth committed (xlsx + CSV); repo layout; PROJECT.md updated; first push |
| 2 | 22 Sep | Verify the 20 rows against the cited pages. Script reads the PDF and prints text/tables from a page |
| 3 | 23 Sep | Script parses the two MP tables (printed pp.44, 49) into rows |
| 4 | 24 Sep | Mapping file (row label -> material, chain_stage, basis...) + extractor writes v2 CSV |
| 5 | 25 Sep | Evaluation: field-level accuracy against the 20 rows |
| 6 | 26 Sep | `raw_text` occurrence check on every row + scale/range checks |
| 7 | 27 Sep | One chart: implied vs stated realised price per REO MT, FY2023–FY2025 |
| 8 | 28 Sep | README: what was checked, what was found, what is known to be wrong |
| 9–10 | 29–30 Sep | Buffer, clean-up, final push |

**Day 7 (the chart) is the milestone that matters.** At that point the repo is
resume-ready and defensible in an interview. Everything after strengthens it and
is optional.

Build in pipeline order: ingest, parse, numeric lane, evaluation, chart. Not the
interface.

**Quit point:** if there is no chart in the repo by 30 September, stop and do
something else. A defined exit makes continuing a choice rather than an
obligation.

---

## Ground truth

Before writing code: 20 rows extracted by hand from the source documents,
recorded in the v2 spreadsheet.

This is not busywork. It is the test set. When the extractor runs, accuracy is
measured against these rows, which means knowing on day one which fields fail
and why, rather than eyeballing output and hoping.

**Pick the rows adversarially.** Twenty clean rows from one well-formatted table
will report 95% accuracy and teach nothing. Include:

- a figure split across a page break
- a restated prior-year comparative (`is_comparative = TRUE`)
- a number in a footnote
- a blended product line with no honest single `chain_stage`
- a scale header ("in thousands") that is easy to miss
- at least one that required thinking

The test set's job is to fail.

It also becomes a line in the README that almost no portfolio project can write:
*evaluated against N hand-verified extractions, field-level accuracy X%.*

---

## Working rules

**Do not commit code that cannot be explained line by line.** Type code out
rather than pasting it. Where a line is not understood, stop and find out what
it does before it goes in the repo.

**Ten documents does not justify a pipeline.** By hand is faster at that scale.
The pipeline pays for itself past thirty or forty documents, and its value
before then is that it is repeatable and auditable — every number traceable to a
page, every check re-runnable.

**Design for 200 documents.** A system that only works on ten hand-picked files
reads as a demo.

**Finish small rather than abandon large.** A four-week project with a chart and
a measured accuracy number beats a twenty-week project with an empty table.

**IP boundary.** Any work done at N.A.N. MagneTech using company data belongs to
the company. This repository uses only publicly available documents. Internal
cost models, vendor coordination, customer agreements and internal planning
material stay out entirely — not in a private repo that syncs, not in commit
messages, not in the README. Confirm before publishing.

**Ask the domain expert for sanity checks, not permission.** Showing a chart to
someone who has the shape of the market in their head catches in two minutes
what would take a week to find alone.

---

## Open questions

- Does Lynas state sales volume separately from production volume in the annual
  report, or is the Q4 quarterly also needed?
- Does Neo Performance Materials disclose sales tonnage?
- Bill of materials per grade — how much Nd, Pr, Dy, Fe, B per kg of N48H?
  Published in the literature; needs sourcing and recording.
- Typical sintered magnet machining yield, for the physical floor calculation.
- Plausible price ranges per material, era-aware, for automated range checks.
- Does MP's FY2024 10-K state an NdPr Realized Price per kg? If so, the withdrawn
  series can be partially reconstructed from earlier filings.
