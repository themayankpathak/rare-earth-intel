import re

# A number as printed in the 10-K: 41,992 or 15.7 or (2,789) for a negative.
NUMBER = re.compile(r"^\(?\d{1,3}(,\d{3})*(\.\d+)?\)?$")
# A footnote marker stuck to the end of a label, like "SEG+(1)".
FOOTNOTE = re.compile(r"\(\d\)$")
# What the 10-K prints for "no value in this column": dashes, and "N/A" (e.g. NdPr volumes before 2023).
EMPTY = {"—", "–", "-", "N/A"}


def is_value(token):
    # True if this piece of text is a number or an empty placeholder.
    return bool(NUMBER.match(token)) or token in EMPTY


def to_number(token):
    # Turn printed text into a number: "41,992" -> 41992.0, "(2,789)" -> -2789.0, "—" or "N/A" -> None.
    if token in EMPTY:
        return None
    negative = token.startswith("(")
    digits = token.strip("()").replace(",", "")
    number = float(digits)
    return -number if negative else number


def parse_line(line, max_values=3):
    # Split one line into its label and up to max_values values (one per year column),
    # each value kept as (printed text, number).
    tokens = line.split()

    # Everything before the first "$" or number is the label.
    # Dot leaders ("Revenue . . . . $ 640,298", Neo 2022-2024) are not part of the label.
    label_words = []
    i = 0
    while i < len(tokens) and tokens[i] != "$" and not is_value(tokens[i]):
        if set(tokens[i]) != {"."}:
            label_words.append(tokens[i])
        i += 1
    label = FOOTNOTE.sub("", " ".join(label_words)).strip()

    values = []
    dollar = False
    for token in tokens[i:]:
        # A "%" belongs to the number just before it: keep it in the printed text ("15.7 %").
        if token == "%" and values:
            raw, number = values[-1]
            values[-1] = (raw + " %", number)
        # One value per year column collected: stop reading this line (the rest are change columns).
        elif len(values) == max_values:
            break
        # A "$" belongs to the number right after it.
        elif token == "$":
            dollar = True
        elif is_value(token):
            raw = "$ " + token if dollar else token
            values.append((raw, to_number(token)))
            dollar = False
    return label, values


if __name__ == "__main__":
    # Real lines from the 10-K. The first six must give the same result as before the "%" change.
    tests = [
        "Rare earth concentrate $ 41,992 $ 144,363 $ 252,468 $ (102,371) $ (108,105) (71) % (43) %",
        "Intersegment eliminations(1) (2,789) — — (2,789) — N/M N/M",
        "REO Sales Volume (MTs) 8,922 32,703 36,837 (23,781) (4,134) (73) % (11) %",
        "Price protection agreement income $ 51,016 $ — $ — $ 51,016 $ — N/M N/M",
        "Rare earth concentrate(1)",
        "(in thousands, except percentages) 2025 2024 2023 2024 2023 2024 2023",
        "Neodymium-Praseodymium 15.7 %",
        "SEG+(1) 1.8 %",
        "NdPr Production Volume (MTs) 1,294 200 N/A 1,094 N/A 547 % N/A",
        "NdPr Realized Price per KG $ 51 $ 70 N/A $ (19) N/A (27)% N/A",
    ]
    for line in tests:
        print(parse_line(line))
    # Lynas: four year columns, then a percentage change.
    print(parse_line("Sales revenue (A$m) 977.9 556.5 463.3 739.3 75.7%", max_values=4))
    # Neo 2022: dot leaders, then year, year, $ change, % change, quarter, quarter...
    print(parse_line("Sales volume (tonnes) . . . . . 13,118 15,103 (1,985) (13.1%) 3,193 3,311 (118) (3.6%)", max_values=2))
