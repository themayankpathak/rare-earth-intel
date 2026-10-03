import collections
import re
import sys
import pdfplumber
import pandas as pd
from text_cleaner import EMPTY, parse_line

def find_page(texts, anchors, document="this document"):
    # anchors: one or more alternatives separated by " | ", tried in order (newer wording first).
    # An alternative can require several phrases on the same page, joined by " && "
    # ("10.1 Magnequench && Sales volume (tonnes)": the segment page, not the table of contents).
    # Return the one page (counting from 1) that matches the first alternative found.
    # Line breaks are flattened first, so a phrase split over two lines still matches.
    for anchor in anchors.split(" | "):
        phrases = anchor.split(" && ")
        pages = [i + 1 for i, text in enumerate(texts)
                 if all(phrase in " ".join(text.split()) for phrase in phrases)]
        if len(pages) > 1:
            sys.exit(f"STOP: '{anchor}' found on several pages {pages} of {document}. Make the anchor more specific.")
        if pages:
            return pages[0]
    return None


def printed_page_number(text):
    # The page number printed in the footer: a number at the end or start of the last line,
    # or of the line before it when the very last line is a label ("... Financial Report 11" / "Appendix 4E").
    # "44" (10-K) / "Lynas Rare Earths Limited | 2026 Annual Report 65" / "18 www.LynasRareEarths.com"
    # A page number has one to three digits, so a year ("February 2026") is never taken for one.
    def page_number(word):
        return word.isdigit() and len(word) <= 3
    lines = text.strip().splitlines()
    last_lines = list(reversed(lines[-2:]))
    for line in last_lines:
        words = line.split()
        for word in (words[-1:] + words[:1]):
            if page_number(word):
                return int(word)
    # Number in the middle of the footer: "Neo Performance Materials Inc. 18 2025 Management's ..."
    for word in last_lines[0].split():
        if page_number(word):
            return int(word)
    # Page number in the header instead (USGS chapters: "133" as the first line; "14 5" when the PDF spaces
    # its digits apart).
    first = lines[0].replace(" ", "") if lines else ""
    if page_number(first):
        return int(first)
    return None


MONTHS = {"January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"}


def year_runs(line):
    # Every run of year columns in a header line, in the order printed. A run is two or more years
    # stepping by one in the same direction:
    #   "2024 2023 2022 2024 vs. 2023"        -> [FY2024, FY2023, FY2022]   (10-K, newest first)
    #   "FY26 FY25 FY24 FY23 change"           -> [FY2026 ... FY2023]   (Lynas)
    #   "2022 2023 2024 2025 2026"             -> [FY2022 ... FY2026]   (Lynas five-year table, oldest first)
    #   "30 June 2017 30 June 2018 ..."        -> [FY2017, FY2018, ...]   (day and month words are skipped)
    #   "2025 2024 2023 2025 2024 2023"        -> [FY2025, FY2024, FY2023], [FY2025, FY2024, FY2023]
    #   "2025 2024 % 2025 2024 %"              -> [FY2025, FY2024], [FY2025, FY2024]   (Neo: quarter, year)
    runs, run = [], []
    for token in line.split():
        # Skip day and month words ("30", "June"): a year is four digits or "FY" plus two digits.
        if token in MONTHS or (token.isdigit() and len(token) <= 2):
            continue
        match = re.fullmatch(r"(?:FY)?((?:19|20)\d\d|\d\d)", token)
        year = None
        if match:
            digits = match.group(1)
            year = int(digits) if len(digits) == 4 else (2000 + int(digits) if token.startswith("FY") else None)
        steps_on = year is not None and run and (len(run) < 2 and abs(year - run[-1]) == 1
                                                 or len(run) >= 2 and year - run[-1] == run[-1] - run[-2])
        if steps_on:
            run.append(year)
            continue
        if len(run) >= 2:
            runs.append(run)
        run = [year] if year is not None else []
    if len(run) >= 2:
        runs.append(run)
    return [[f"FY{y}" for y in r] for r in runs]


def years_in_header(line):
    # The first run of year columns in a header line, or [] if there is none.
    runs = year_runs(line)
    return runs[0] if runs else []


def quarter_first(line):
    # True if this header puts a "Three Months Ended" block before the "Year Ended" block (Neo 2024-25);
    # False if the year comes first (Neo 2022-23) or the line names no quarter block at all.
    year_at = max(line.find("Year Ended"), line.find("Year ended"))
    quarter_at = line.find("Three Months")
    return quarter_at != -1 and year_at != -1 and quarter_at < year_at


def column_layout(line, quarter_block_first):
    # From a header line, which year columns hold full-year figures, and how many values come before them.
    # Returns (years, skip) or None if the line is not a header.
    runs = year_runs(line)
    if not runs:
        return None
    if quarter_block_first and len(runs) >= 2:
        return runs[1], len(runs[0])   # quarter block first: the full year is the second block
    return runs[0], 0


def is_header(line, label, values):
    # A line with no values, or no label, may be a table header naming the year columns.
    # "30 June 2019 30 June 2020 ..." has no label: it starts with "30", so it reads as numbers at first.
    scale_line = "in thousands" in line or "in whole units" in line
    return (scale_line or not values or not label) and bool(year_runs(line))


def extract_page(text, table, pdf_page, years, scale, estimates):
    # Read one page top to bottom and return one row per number.
    # years: the year columns until a header says otherwise ("none" tables keep ["not_applicable"]).
    # scale: starting scale, for pages with no scale line.
    printed_page = printed_page_number(text)
    group = None
    rows = []
    skip = 0                     # values to pass over before the full-year columns (Neo: the quarter block)
    has_years = years != ["not_applicable"]
    lines = text.splitlines()

    # Look at the page's first table header before reading any rows: the text of a page does not always
    # come out in reading order, and a header can follow its own rows (Neo FY2024 reconciliation table).
    order = False
    if has_years:
        for line in lines:
            order = quarter_first(line) or order
            label, values = parse_line(line, max_values=100)
            if is_header(line, label, values):
                years, skip = column_layout(line, order)
                break
    order = False
    block_estimated = False

    for line in lines:
        # A scale line ("in thousands", "in whole units") applies to every number below it.
        is_scale_line = "in thousands" in line or "in whole units" in line
        if is_scale_line:
            scale = 1000 if "in thousands" in line else 1
        # "Three Months Ended ... Year Ended" says which block of columns comes first.
        if "Three Months" in line and ("Year Ended" in line or "Year ended" in line):
            order = quarter_first(line)

        label, values = parse_line(line, max_values=100)
        if has_years and is_header(line, label, values):
            years, skip = column_layout(line, order)
            continue
        # A line of quarter labels ("amounts) Q4 Q3 Q2 Q1 Q4 Q3 Q2 Q1") means the columns below are quarters,
        # even if the line above said "2025 2024": take no full-year values until the next real header.
        words = line.split()
        quarters = [w for w in words if re.fullmatch(r"Q[1-4]", w)]
        if has_years and len(quarters) >= 2 and len(quarters) * 2 >= len(words):
            years = []
            continue
        if is_scale_line or not label:
            continue
        # A line with no numbers starts a new block: estimated throughout if its heading is marked "e".
        if not values:
            block_estimated = line in estimates["marked"]
        # A short line with no numbers is a heading: remember it as the group.
        if not values:
            if len(label.split()) < 6 and not label.endswith("."):
                group = label
            continue

        # Each value's estimate mark ("e"), if the publisher printed one (USGS); otherwise no marks.
        flags = estimates["lines"].get(line, [])
        flags = flags if len(flags) == len(values) else [False] * len(values)
        values = [(raw, number, flag) for (raw, number), flag in zip(values, flags)]

        # Keep the full-year values: drop percentages (change columns), pass over the quarter block,
        # then pair each value with its year column, left to right.
        if has_years:
            values = [v for v in values if not v[0].endswith("%")]
        values = values[skip:skip + len(years)]
        for year, (raw, number, flag) in zip(years, values):
            rows.append({
                "table": table,
                "printed_page": printed_page,
                "pdf_page": pdf_page,
                "group": group,
                "label": label,
                "period": year,
                "raw_text": raw,
                "value_reported": number,
                "scale_factor": scale,
                "estimate": flag or year in estimates["years"] or block_estimated or line in estimates["marked"],
            })
    return rows


def superscript_size(page):
    # Characters smaller than this are superscripts (footnote numbers, "e" for estimated): under three
    # quarters of the page's most common text size (USGS: 5 and 6.5 point against 10 point).
    sizes = collections.Counter(round(c["size"], 1) for c in page.chars)
    return 0.75 * sizes.most_common(1)[0][0]


def value_like(token):
    # A token in the original line that holds a table value: a number (possibly with a footnote or an "e"
    # glued on) or a placeholder such as "—", "NA" or "W".
    return bool(re.fullmatch(r"e?\d[\d,.]*", token)) or token in EMPTY


def read_page(page, drop_superscripts):
    # The page's text, plus which values the publisher marked as estimates.
    # With drop_superscripts (USGS), small characters are removed first, so a footnote glued to a number
    # ("Australia 1216,000" = footnote 12 + 16,000) no longer changes the number. The removed "e" marks
    # are kept as estimate flags: per line, one flag per value, and the years whose column header says "e".
    if not drop_superscripts:
        return page.extract_text() or "", {"years": set(), "lines": {}, "marked": set()}
    size = superscript_size(page)
    clean = page.filter(lambda o: o.get("object_type") != "char" or o["size"] >= size)
    original_lines = page.extract_text_lines()
    estimates = {"years": set(), "lines": {}, "marked": set()}
    for line in original_lines:
        estimates["years"] |= {f"FY{y}" for y in re.findall(r"\b(\d{4})e\b", line["text"])}
    for line in clean.extract_text_lines():
        # The same line before the superscripts were removed: the one at the same height on the page.
        original = min(original_lines, key=lambda o: abs(o["top"] - line["top"]))
        flags = [token.startswith("e") for token in original["text"].split() if value_like(token)]
        estimates["lines"][line["text"]] = flags
        # A superscript "e" right after a word ("Mine production" + e, "Production:" + e) marks everything
        # that heading covers as estimated, not just one number.
        chars = original["chars"]
        if any(c["text"] == "e" and c["size"] < size and i > 0 and not chars[i - 1]["text"].isdigit()
               for i, c in enumerate(chars)):
            estimates["marked"].add(line["text"])
    return clean.extract_text() or "", estimates


def read_pdf(path, drop_superscripts):
    # Read the text of every page once (slow on long filings: a minute or two).
    with pdfplumber.open(path) as pdf:
        pages = [read_page(page, drop_superscripts) for page in pdf.pages]
    return [text for text, _ in pages], [estimates for _, estimates in pages]


def main(company_name, filing):
    # Read one document of one source, e.g. main("lynas", "FY2026"), and save one row per number.
    company = pd.read_csv("config/companies.csv", dtype=str).set_index("company").loc[company_name]
    pdf_path = f"data/raw/{company['file_prefix']}_{filing}.pdf"
    tables_file = f"config/{company_name}_tables.csv"  # which tables to read, and the text that finds each page
    output = f"data/interim/{company_name}_extracted_rows_{filing}.csv"

    # Until a table header says otherwise, assume the filing year and the two years before it.
    year = int(filing[2:])
    default_years = [f"FY{year}", f"FY{year - 1}", f"FY{year - 2}"]

    print(f"Reading {pdf_path} ...")
    texts, estimates = read_pdf(pdf_path, company["superscripts"] == "drop")

    # Read the tables in the order they are listed in the tables file (this order sets the row_ids).
    tables = pd.read_csv(tables_file, dtype=str).fillna("")
    rows = []
    for _, t in tables.iterrows():
        pdf_page = find_page(texts, t["anchor"], filing)
        if pdf_page is None:
            print(f"  {t['table']:<13} not in this filing, skipped")
            continue
        # Year columns: read from the table header, or none (the composition table has no year).
        years = default_years if t["years"] == "header" else ["not_applicable"]
        scale = int(t["start_scale"]) if t["start_scale"] else None
        found = extract_page(texts[pdf_page - 1], t["table"], pdf_page, years, scale, estimates[pdf_page - 1])
        print(f"  {t['table']:<13} pdf p.{pdf_page} (printed p.{printed_page_number(texts[pdf_page - 1])}): {len(found)} values")
        rows += found

    table = pd.DataFrame(rows)
    table.to_csv(output, index=False)
    print(f"{len(table)} rows saved to {output}")


# Run from the terminal: python scripts/extract_rows.py lynas FY2026
# (Loading this file from a test does not run anything; the tests call the functions directly.)
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
