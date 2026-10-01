import re

# A number as printed in the 10-K: 41,992 or 15.7 or (2,789) for a negative.
NUMBER = re.compile(r"^\(?\d{1,3}(,\d{3})*(\.\d+)?\)?$")
# A footnote marker stuck to the end of a label, like "SEG+(1)".
FOOTNOTE = re.compile(r"\(\d\)$")
# Dashes the 10-K prints for "nothing here".
DASHES = {"—", "–", "-"}


def is_value(token):
    # True if this piece of text is a number or a dash.
    return bool(NUMBER.match(token)) or token in DASHES


def to_number(token):
    # Turn printed text into a number: "41,992" -> 41992.0, "(2,789)" -> -2789.0, "—" -> None.
    if token in DASHES:
        return None
    negative = token.startswith("(")
    digits = token.strip("()").replace(",", "")
    number = float(digits)
    return -number if negative else number


def parse_line(line):
    # Split one line into its label and up to three values, each value kept as (printed text, number).
    tokens = line.split()

    # Everything before the first "$" or number is the label.
    label_words = []
    i = 0
    while i < len(tokens) and tokens[i] != "$" and not is_value(tokens[i]):
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
        # Three values collected (the three year columns): stop reading this line.
        elif len(values) == 3:
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
    ]
    for line in tests:
        print(parse_line(line))